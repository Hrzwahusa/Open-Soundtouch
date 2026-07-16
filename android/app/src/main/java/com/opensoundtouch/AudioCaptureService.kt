package com.opensoundtouch

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.AudioFormat
import android.media.AudioPlaybackCaptureConfiguration
import android.media.AudioRecord
import android.media.VolumeProvider
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Build
import android.os.IBinder
import androidx.annotation.RequiresApi
import com.opensoundtouch.data.SoundTouchClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import java.io.OutputStream
import java.net.ServerSocket
import java.net.Socket

/**
 * Phase 5 — streams the phone's own playback audio to a SoundTouch speaker.
 *
 * Captures system audio via MediaProjection + AudioPlaybackCapture (API 29+),
 * wraps the raw PCM in a streaming WAV, and serves it over a tiny embedded HTTP
 * server. The speaker plays it via DLNA (http://<phone-ip>:PORT/stream.wav).
 *
 * Volume: the foreground notification carries -/+ actions (they also show on the
 * lock screen via MediaStyle) that change the whole group relatively. Hardware
 * keys work in-app; a system-wide capture of them is not possible on Samsung
 * (One UI doesn't deliver volume keys to accessibility, and the captured app owns
 * the media session), so the notification controls are the reliable path.
 */
class AudioCaptureService : Service() {

    companion object {
        const val PORT = 8899
        const val ACTION_START = "com.opensoundtouch.CAPTURE_START"
        const val ACTION_STOP = "com.opensoundtouch.CAPTURE_STOP"
        const val ACTION_VOL_UP = "com.opensoundtouch.VOL_UP"
        const val ACTION_VOL_DOWN = "com.opensoundtouch.VOL_DOWN"
        const val EXTRA_RESULT_CODE = "resultCode"
        const val EXTRA_RESULT_DATA = "resultData"
        const val EXTRA_BOX_IP = "boxIp"
        const val EXTRA_INIT_VOLUME = "initVolume"
        const val EXTRA_MEMBER_IPS = "memberIps"
        const val EXTRA_MUTE_LOCAL = "muteLocal"

        // Unofficial but widely-supported system broadcast for volume changes.
        private const val VOLUME_CHANGED = "android.media.VOLUME_CHANGED_ACTION"
        private const val EXTRA_VOL_STREAM = "android.media.EXTRA_VOLUME_STREAM_TYPE"
        private const val EXTRA_VOL_VALUE = "android.media.EXTRA_VOLUME_STREAM_VALUE"

        private const val CHANNEL_ID = "audio_capture"
        private const val NOTIF_ID = 42

        const val SAMPLE_RATE = 44100
        const val CHANNELS = 2
        const val BITS = 16

        @Volatile
        var isRunning: Boolean = false
            private set

        @Volatile
        private var instance: AudioCaptureService? = null

        /** Called from the accessibility service to control volume system-wide. */
        fun adjustVolume(delta: Int) {
            instance?.adjustVolumeInternal(delta)
        }
    }

    @Volatile private var running = false
    private var projection: MediaProjection? = null
    private var record: AudioRecord? = null
    private var serverSocket: ServerSocket? = null
    private var worker: Thread? = null
    private var mediaSession: MediaSession? = null
    private var volumeProvider: VolumeProvider? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var boxIp: String = ""
    private var boxVolume: Int = 0
    private var memberIps: List<String> = emptyList()
    private val memberVols = java.util.concurrent.ConcurrentHashMap<String, Int>()

    // Volume mirroring: map the phone's media-volume key presses to the box(es).
    private var volumeReceiver: BroadcastReceiver? = null
    private var savedPhoneVol: Int = -1
    private var pinnedVol: Int = 0
    private var pinPhone: Boolean = false
    private var lastPhoneVol: Int = 0

    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopEverything()
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_VOL_UP -> {
                adjustVolumeInternal(5)
                return START_STICKY
            }
            ACTION_VOL_DOWN -> {
                adjustVolumeInternal(-5)
                return START_STICKY
            }
        }

        startForegroundNotification()

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            // AudioPlaybackCapture needs API 29+.
            stopSelf()
            return START_NOT_STICKY
        }

        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val data: Intent? = intent?.let {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                it.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
            else
                @Suppress("DEPRECATION") it.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        if (resultCode == 0 || data == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        boxIp = intent?.getStringExtra(EXTRA_BOX_IP) ?: ""
        memberIps = intent?.getStringArrayListExtra(EXTRA_MEMBER_IPS)
            ?: listOfNotNull(boxIp.ifEmpty { null })
        val initVol = intent?.getIntExtra(EXTRA_INIT_VOLUME, 30) ?: 30
        startCapture(resultCode, data)
        if (boxIp.isNotEmpty()) {
            setupMediaSession(initVol)
            startVolumeMirror(intent?.getBooleanExtra(EXTRA_MUTE_LOCAL, false) ?: false)
            refreshNotification()
        }
        return START_STICKY
    }

    /**
     * MediaSession with a remote VolumeProvider — powers the lock-screen media
     * controls and lets hardware keys work while the app is in the foreground.
     */
    private fun setupMediaSession(initVol: Int) {
        boxVolume = initVol.coerceIn(0, 100)
        // Seed each member's current volume so relative changes keep the balance.
        scope.launch {
            memberIps.forEach { m ->
                if (m.isNotEmpty()) SoundTouchClient(m).getVolume()?.actual?.let { memberVols[m] = it }
            }
        }
        val provider = object : VolumeProvider(VolumeProvider.VOLUME_CONTROL_RELATIVE, 100, boxVolume) {
            override fun onAdjustVolume(direction: Int) {
                if (direction != 0) adjustVolumeInternal(direction * 5)
            }

            override fun onSetVolumeTo(volume: Int) {
                adjustVolumeInternal(volume.coerceIn(0, 100) - boxVolume)
            }
        }
        volumeProvider = provider

        val session = MediaSession(this, "OpenSoundTouch")
        session.setPlaybackState(
            PlaybackState.Builder()
                .setState(PlaybackState.STATE_PLAYING, 0L, 1f)
                .setActions(PlaybackState.ACTION_PLAY_PAUSE)
                .build()
        )
        session.setPlaybackToRemote(provider)
        session.isActive = true
        mediaSession = session
    }

    /** Apply a relative volume delta to all member speakers (group-aware). */
    private fun adjustVolumeInternal(delta: Int) {
        if (delta == 0) return
        scope.launch {
            val ips = memberIps.ifEmpty { listOfNotNull(boxIp.ifEmpty { null }) }
            ips.forEach { m ->
                val cur = memberVols[m] ?: SoundTouchClient(m).getVolume()?.actual ?: 20
                val nv = (cur + delta).coerceIn(0, 100)
                if (SoundTouchClient(m).setVolume(nv)) memberVols[m] = nv
            }
            val master = memberVols[boxIp] ?: memberVols.values.firstOrNull() ?: boxVolume
            boxVolume = master
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) volumeProvider?.currentVolume = master
        }
    }

    /**
     * Mirror the phone's media-volume key presses onto the box(es) — works
     * system-wide because the keys always change STREAM_MUSIC. When [mute] is set
     * the phone volume is pinned near-silent and reset after each press, so only
     * the box gets loud (capture stays full quality regardless of the pin).
     */
    private fun startVolumeMirror(mute: Boolean) {
        val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val stream = AudioManager.STREAM_MUSIC
        savedPhoneVol = am.getStreamVolume(stream)
        pinPhone = mute
        pinnedVol = if (mute) 1.coerceAtMost(am.getStreamMaxVolume(stream)) else savedPhoneVol
        lastPhoneVol = pinnedVol
        if (mute) am.setStreamVolume(stream, pinnedVol, 0)

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.action != VOLUME_CHANGED) return
                if (intent.getIntExtra(EXTRA_VOL_STREAM, -1) != stream) return
                val v = intent.getIntExtra(EXTRA_VOL_VALUE, -1)
                if (v < 0) return
                val delta = v - lastPhoneVol
                if (delta == 0) return
                adjustVolumeInternal(delta * 5)
                if (pinPhone) {
                    am.setStreamVolume(stream, pinnedVol, 0)
                    lastPhoneVol = pinnedVol
                } else {
                    lastPhoneVol = v
                }
            }
        }
        val filter = IntentFilter(VOLUME_CHANGED)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(receiver, filter)
        }
        volumeReceiver = receiver
    }

    private fun stopVolumeMirror() {
        volumeReceiver?.let {
            try {
                unregisterReceiver(it)
            } catch (_: Exception) {
            }
        }
        volumeReceiver = null
        if (savedPhoneVol >= 0) {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            am.setStreamVolume(AudioManager.STREAM_MUSIC, savedPhoneVol, 0)
            savedPhoneVol = -1
        }
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun startCapture(resultCode: Int, data: Intent) {
        val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val mp = mpm.getMediaProjection(resultCode, data) ?: run { stopSelf(); return }
        // Android 14 requires a registered callback before capturing.
        mp.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                stopEverything()
                stopSelf()
            }
        }, null)
        projection = mp

        val config = AudioPlaybackCaptureConfiguration.Builder(mp)
            .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
            .addMatchingUsage(AudioAttributes.USAGE_GAME)
            .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
            .build()

        val format = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(SAMPLE_RATE)
            .setChannelMask(AudioFormat.CHANNEL_IN_STEREO)
            .build()

        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_16BIT
        ).coerceAtLeast(8192)

        record = try {
            AudioRecord.Builder()
                .setAudioFormat(format)
                .setBufferSizeInBytes(minBuf * 2)
                .setAudioPlaybackCaptureConfig(config)
                .build()
        } catch (e: SecurityException) {
            stopEverything(); stopSelf(); return
        }

        running = true
        isRunning = true
        worker = Thread { serveLoop(minBuf) }.also { it.isDaemon = true; it.start() }
    }

    /** Accept HTTP connections and stream WAV audio until stopped. */
    private fun serveLoop(bufSize: Int) {
        try {
            val server = ServerSocket(PORT)
            server.reuseAddress = true
            serverSocket = server
            while (running) {
                val client = try {
                    server.accept()
                } catch (e: Exception) {
                    break
                }
                streamTo(client, bufSize)
            }
        } catch (e: Exception) {
            // port busy / socket closed
        } finally {
            stopEverything()
        }
    }

    private fun streamTo(client: Socket, bufSize: Int) {
        try {
            client.getInputStream() // drain request line(s); we ignore them
            val out: OutputStream = client.getOutputStream()
            val header =
                "HTTP/1.1 200 OK\r\n" +
                    "Content-Type: audio/wav\r\n" +
                    "Connection: close\r\n" +
                    "Cache-Control: no-cache\r\n\r\n"
            out.write(header.toByteArray())
            out.write(wavHeader())
            out.flush()

            val rec = record ?: return
            rec.startRecording()
            val buf = ByteArray(bufSize)
            while (running) {
                val n = rec.read(buf, 0, buf.size)
                if (n <= 0) continue
                out.write(buf, 0, n)
            }
        } catch (e: Exception) {
            // client disconnected
        } finally {
            try {
                record?.stop()
            } catch (_: Exception) {
            }
            try {
                client.close()
            } catch (_: Exception) {
            }
        }
    }

    /** Streaming WAV header with "infinite" sizes (0xFFFFFFFF). */
    private fun wavHeader(): ByteArray {
        val byteRate = SAMPLE_RATE * CHANNELS * BITS / 8
        val blockAlign = CHANNELS * BITS / 8
        val h = ByteArray(44)
        fun putStr(off: Int, s: String) {
            for (i in s.indices) h[off + i] = s[i].code.toByte()
        }
        fun putIntLE(off: Int, v: Int) {
            h[off] = (v and 0xFF).toByte()
            h[off + 1] = (v ushr 8 and 0xFF).toByte()
            h[off + 2] = (v ushr 16 and 0xFF).toByte()
            h[off + 3] = (v ushr 24 and 0xFF).toByte()
        }
        fun putShortLE(off: Int, v: Int) {
            h[off] = (v and 0xFF).toByte()
            h[off + 1] = (v ushr 8 and 0xFF).toByte()
        }
        putStr(0, "RIFF")
        putIntLE(4, -1)            // 0xFFFFFFFF (streaming)
        putStr(8, "WAVE")
        putStr(12, "fmt ")
        putIntLE(16, 16)           // PCM fmt chunk size
        putShortLE(20, 1)          // PCM
        putShortLE(22, CHANNELS)
        putIntLE(24, SAMPLE_RATE)
        putIntLE(28, byteRate)
        putShortLE(32, blockAlign)
        putShortLE(34, BITS)
        putStr(36, "data")
        putIntLE(40, -1)           // 0xFFFFFFFF (streaming)
        return h
    }

    private fun stopEverything() {
        running = false
        isRunning = false
        stopVolumeMirror()
        try {
            serverSocket?.close()
        } catch (_: Exception) {
        }
        serverSocket = null
        try {
            record?.stop()
        } catch (_: Exception) {
        }
        try {
            record?.release()
        } catch (_: Exception) {
        }
        record = null
        try {
            projection?.stop()
        } catch (_: Exception) {
        }
        projection = null
        try {
            mediaSession?.isActive = false
            mediaSession?.release()
        } catch (_: Exception) {
        }
        mediaSession = null
        volumeProvider = null
    }

    override fun onDestroy() {
        stopEverything()
        instance = null
        scope.cancel()
        super.onDestroy()
    }

    // ---- Notification with volume controls -------------------------------

    private fun servicePendingIntent(action: String, requestCode: Int): PendingIntent {
        val i = Intent(this, AudioCaptureService::class.java).setAction(action)
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        return PendingIntent.getService(this, requestCode, i, flags)
    }

    private fun buildNotification(): Notification {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, getString(R.string.svc_channel), NotificationManager.IMPORTANCE_LOW)
            )
        }
        val builder = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.svc_text))
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setOngoing(true)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .addAction(
                android.R.drawable.ic_media_rew, getString(R.string.svc_quieter),
                servicePendingIntent(ACTION_VOL_DOWN, 1),
            )
            .addAction(
                android.R.drawable.ic_media_ff, getString(R.string.svc_louder),
                servicePendingIntent(ACTION_VOL_UP, 2),
            )
            .addAction(
                android.R.drawable.ic_menu_close_clear_cancel, getString(R.string.svc_stop),
                servicePendingIntent(ACTION_STOP, 3),
            )
        mediaSession?.let { s ->
            builder.setStyle(
                Notification.MediaStyle()
                    .setMediaSession(s.sessionToken)
                    .setShowActionsInCompactView(0, 1)
            )
        }
        return builder.build()
    }

    private fun startForegroundNotification() {
        val notif = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    private fun refreshNotification() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID, buildNotification())
    }
}