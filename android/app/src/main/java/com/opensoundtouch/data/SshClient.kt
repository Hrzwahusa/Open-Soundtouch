package com.opensoundtouch.data

import com.jcraft.jsch.ChannelExec
import com.jcraft.jsch.JSch
import com.jcraft.jsch.Session
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Kotlin/JSch port of device_ssh.py: manages the on-device preset configuration
 * over SSH (Dropbear, root without password).
 *
 * The speaker uses a legacy Dropbear with ssh-rsa host keys, so we explicitly
 * re-enable ssh-rsa (the maintained JSch fork disables it by default) and skip
 * host-key checking (matches the desktop's StrictHostKeyChecking=no).
 *
 * File transfer is cat-over-SSH (no scp) because Dropbear has no sftp-server.
 * Preset config format:  N|URL|NAME   (N = 1..6)
 */
class SshClient(private val ip: String, private val user: String = "root") {

    companion object {
        const val CONF_PATH = "/mnt/nv/preset_proxies.conf"
        private const val LEGACY = "ssh-rsa,rsa-sha2-256,rsa-sha2-512,ecdsa-sha2-nistp256,ssh-ed25519"
    }

    /** Fast TCP check whether SSH (port 22) is reachable. */
    suspend fun isReachable(timeoutMs: Int = 3000): Boolean = withContext(Dispatchers.IO) {
        try {
            Socket().use { it.connect(InetSocketAddress(ip, 22), timeoutMs); true }
        } catch (e: Exception) {
            false
        }
    }

    private fun openSession(): Session {
        val session = JSch().getSession(user, ip, 22)
        session.setPassword("") // Dropbear root, no password
        session.setConfig("StrictHostKeyChecking", "no")
        session.setConfig("server_host_key", LEGACY)
        session.setConfig("PubkeyAcceptedAlgorithms", "+ssh-rsa")
        session.setConfig("PreferredAuthentications", "password,keyboard-interactive,none")
        session.connect(8000)
        return session
    }

    /** Run a command; returns (exitCode, stdout+stderr). exitCode -1 on failure. */
    private suspend fun run(command: String): Pair<Int, String> = withContext(Dispatchers.IO) {
        var session: Session? = null
        try {
            session = openSession()
            val channel = session.openChannel("exec") as ChannelExec
            channel.setCommand(command)
            val err = ByteArrayOutputStream()
            channel.setErrStream(err)
            val input = channel.inputStream
            channel.connect(8000)
            val out = input.readBytes()
            while (!channel.isClosed) Thread.sleep(20)
            val code = channel.exitStatus
            channel.disconnect()
            code to (String(out) + err.toString())
        } catch (e: Exception) {
            -1 to (e.message ?: "ssh error")
        } finally {
            session?.disconnect()
        }
    }

    /** Read a file's content (or null). */
    private suspend fun readFile(path: String): String? {
        val (code, out) = run("cat '$path' 2>/dev/null")
        return if (code == 0) out else null
    }

    /** Write content via cat-over-SSH (LF-normalised). */
    private suspend fun writeFile(path: String, content: String): Boolean = withContext(Dispatchers.IO) {
        val bytes = content.replace("\r\n", "\n").toByteArray()
        var session: Session? = null
        try {
            session = openSession()
            val channel = session.openChannel("exec") as ChannelExec
            channel.setCommand("cat > '$path'")
            val stdin = channel.outputStream
            channel.connect(8000)
            stdin.write(bytes)
            stdin.flush()
            stdin.close()
            while (!channel.isClosed) Thread.sleep(20)
            val code = channel.exitStatus
            channel.disconnect()
            code == 0
        } catch (e: Exception) {
            false
        } finally {
            session?.disconnect()
        }
    }

    // ---- Preset configuration --------------------------------------------

    suspend fun readPresets(): Map<Int, Preset> {
        val txt = readFile(CONF_PATH) ?: return emptyMap()
        val map = LinkedHashMap<Int, Preset>()
        txt.lineSequence().forEach { raw ->
            val line = raw.trim()
            if (line.isEmpty() || line.startsWith("#")) return@forEach
            val parts = line.split("|")
            if (parts.size >= 2) {
                val n = parts[0].toIntOrNull() ?: return@forEach
                val name = if (parts.size > 2) parts[2] else "Preset $n"
                map[n] = Preset(n, parts[1], name)
            }
        }
        return map
    }

    private suspend fun writePresets(presets: Map<Int, Preset>): Boolean {
        val sb = StringBuilder()
        sb.append("# Preset configuration (managed by the app)\n")
        sb.append("# Format: N|URL|NAME   (N = preset 1..6)\n\n")
        presets.keys.sorted().forEach { n ->
            val p = presets.getValue(n)
            val url = p.url.replace("|", "%7C").replace("\n", "").trim()
            val name = p.name.replace("|", " ").replace("\n", " ").trim()
            if (url.isNotEmpty()) sb.append("$n|$url|$name\n")
        }
        return writeFile(CONF_PATH, sb.toString())
    }

    /** Create/update preset N (read-modify-write of the on-device config). */
    suspend fun setPreset(n: Int, url: String, name: String): Boolean {
        if (url.isBlank()) return false
        val presets = readPresets().toMutableMap()
        presets[n] = Preset(n, url, name.ifBlank { "Preset $n" })
        return writePresets(presets)
    }

    /** Remove preset N from the config. */
    suspend fun clearPreset(n: Int): Boolean {
        val presets = readPresets().toMutableMap()
        presets.remove(n)
        return writePresets(presets)
    }
}