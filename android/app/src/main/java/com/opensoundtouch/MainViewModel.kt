package com.opensoundtouch

import android.app.Application
import android.content.Intent
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.opensoundtouch.data.Device
import com.opensoundtouch.data.DeviceStore
import com.opensoundtouch.data.Discovery
import com.opensoundtouch.data.DlnaClient
import com.opensoundtouch.data.Favorite
import com.opensoundtouch.data.FavoritesStore
import com.opensoundtouch.data.GroupStore
import com.opensoundtouch.data.NowPlaying
import com.opensoundtouch.data.Preset
import com.opensoundtouch.data.SavedGroup
import com.opensoundtouch.data.SoundTouchClient
import com.opensoundtouch.data.SshClient
import com.opensoundtouch.data.Station
import com.opensoundtouch.data.TuneInClient
import com.opensoundtouch.data.ZoneMember
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class UiState(
    val scanning: Boolean = false,
    val devices: List<Device> = emptyList(),
    val selected: Device? = null,
    val nowPlaying: NowPlaying? = null,
    val volume: Int? = null,
    val status: String = "Bereit",
    val searchBusy: Boolean = false,
    val searchResults: List<Station> = emptyList(),
    val favorites: List<Favorite> = emptyList(),
    val savedGroups: List<SavedGroup> = emptyList(),
    val selectedGroup: SavedGroup? = null,
    val memberVolumes: Map<String, Int> = emptyMap(),
    val sshReachable: Boolean? = null,
    val presets: Map<Int, Preset> = emptyMap(),
    val capturing: Boolean = false,
)

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private val dlna = DlnaClient()
    private val tunein = TuneInClient()
    private val favStore = FavoritesStore(app)
    private val groupStore = GroupStore(app)
    private val deviceStore = DeviceStore(app)

    init {
        _state.value = _state.value.copy(
            favorites = favStore.load(),
            savedGroups = groupStore.load(),
            devices = deviceStore.load(),
        )
    }

    /** Merge devices into the saved list (union by IP, newest info wins) and persist. */
    private fun rememberDevices(found: List<Device>) {
        if (found.isEmpty()) return
        val byIp = LinkedHashMap<String, Device>()
        _state.value.devices.forEach { byIp[it.ip] = it }
        found.forEach { byIp[it.ip] = it }
        val merged = byIp.values.sortedBy { it.name.lowercase() }
        deviceStore.save(merged)
        _state.value = _state.value.copy(devices = merged)
    }

    fun forgetDevice(device: Device) {
        val next = _state.value.devices.filterNot { it.ip == device.ip }
        deviceStore.save(next)
        _state.value = _state.value.copy(devices = next)
    }

    /** Rename the selected single speaker (not available for a group). */
    fun renameDevice(newName: String) {
        val dev = _state.value.selected ?: return
        if (_state.value.selectedGroup != null) return
        val name = newName.trim()
        if (name.isEmpty()) return
        viewModelScope.launch {
            if (SoundTouchClient(dev.ip).setName(name)) {
                val updated = dev.copy(name = name)
                val devs = _state.value.devices.map { if (it.ip == dev.ip) updated else it }
                deviceStore.save(devs)
                _state.value = _state.value.copy(
                    selected = updated, devices = devs, status = "Umbenannt: $name",
                )
            } else {
                _state.value = _state.value.copy(
                    status = "Umbenennen fehlgeschlagen: ${SoundTouchClient.lastError ?: "?"}",
                )
            }
        }
    }

    private fun client(): SoundTouchClient? =
        _state.value.selected?.let { SoundTouchClient(it.ip) }

    fun discover() {
        _state.value = _state.value.copy(scanning = true, status = "Suche Geräte…")
        viewModelScope.launch {
            val devices = Discovery.scan()
            // Merge with saved devices so standby speakers (not found by the scan)
            // stay selectable instead of disappearing.
            rememberDevices(devices)
            _state.value = _state.value.copy(
                scanning = false,
                status = if (devices.isEmpty()) "Keine neuen gefunden (gespeicherte bleiben)" else "${devices.size} gefunden",
            )
        }
    }

    fun select(device: Device) {
        val active = _state.value.selectedGroup
        if (active != null) {
            viewModelScope.launch {
                val master = SoundTouchClient(active.masterIp)
                active.slaves.forEach { master.removeZoneSlave(active.masterMac, it.mac) }
            }
        }
        _state.value = _state.value.copy(
            selected = device, selectedGroup = null, memberVolumes = emptyMap(),
            sshReachable = null, presets = emptyMap(),
            status = "Verbunden: ${device.name}",
        )
        refresh()
    }

    /**
     * Direkt per IP verbinden (Fallback zur Discovery). Nötig z. B. im Android-
     * Emulator, dessen NAT-WLAN (10.0.2.x) das echte LAN nicht scannt – eine
     * direkte Verbindung zur bekannten Box-IP wird aber via Host geroutet.
     */
    fun addByIp(ip: String) {
        val clean = ip.trim()
        if (clean.isEmpty()) return
        _state.value = _state.value.copy(status = "Verbinde zu $clean …")
        viewModelScope.launch {
            val dev = SoundTouchClient(clean).getInfo()
            if (dev != null) {
                rememberDevices(listOf(dev))
                select(dev)
            } else {
                _state.value = _state.value.copy(status = "Kein Gerät unter $clean erreichbar")
            }
        }
    }

    fun deselect() {
        _state.value = _state.value.copy(selected = null, nowPlaying = null, volume = null)
    }

    fun refresh() {
        val c = client() ?: return
        viewModelScope.launch {
            val np = c.getNowPlaying()
            val vol = c.getVolume()?.actual
            _state.value = _state.value.copy(nowPlaying = np, volume = vol)
        }
    }

    fun sendKey(key: String) {
        val c = client() ?: return
        viewModelScope.launch {
            val ok = c.sendKey(key)
            if (!ok) {
                _state.value = _state.value.copy(
                    status = "Taste $key fehlgeschlagen: ${SoundTouchClient.lastError ?: "?"}",
                )
            }
            refresh()
        }
    }

    fun changeVolume(delta: Int) {
        val c = client() ?: return
        viewModelScope.launch {
            // Prefer the cached volume so we need only ONE connection (the set),
            // which the single-connection on-device proxy handles far more reliably.
            val cur = _state.value.volume ?: c.getVolume()?.actual
            if (cur == null) {
                _state.value = _state.value.copy(
                    status = "Lautstärke lesen fehlgeschlagen: ${SoundTouchClient.lastError ?: "?"}",
                )
                return@launch
            }
            val next = (cur + delta).coerceIn(0, 100)
            if (c.setVolume(next)) {
                _state.value = _state.value.copy(volume = next, status = "Lautstärke $next")
            } else {
                _state.value = _state.value.copy(
                    status = "Lautstärke setzen fehlgeschlagen: ${SoundTouchClient.lastError ?: "?"}",
                )
            }
        }
    }

    // ---- Internet radio: search / play / favorites ------------------------

    fun search(query: String) {
        if (query.isBlank()) return
        _state.value = _state.value.copy(searchBusy = true, status = "Suche „$query“…")
        viewModelScope.launch {
            val results = tunein.search(query)
            _state.value = _state.value.copy(
                searchBusy = false,
                searchResults = results,
                status = if (results.isEmpty()) "Keine Sender gefunden" else "${results.size} Sender",
            )
        }
    }

    /** Play a station: resolve its stream URL (guide id / path / direct) then DLNA. */
    fun playStation(idOrUrl: String, name: String) {
        val dev = _state.value.selected ?: return
        _state.value = _state.value.copy(status = "Löse Stream auf …")
        viewModelScope.launch {
            val stream = tunein.resolveStreamUrl(idOrUrl)
            if (stream == null) {
                _state.value = _state.value.copy(status = "Stream für „$name“ nicht auflösbar")
                return@launch
            }
            val ok = dlna.playUrl(dev.ip, stream, title = name)
            _state.value = _state.value.copy(status = if (ok) "📻 $name" else "Wiedergabe fehlgeschlagen")
            refresh()
        }
    }

    fun playFavorite(fav: Favorite) {
        val target = fav.url.ifBlank { fav.guideId }
        playStation(target, fav.name)
    }

    /** Play a raw stream URL typed by the user (DLNA). */
    fun playUrl(url: String) {
        if (!url.startsWith("http")) {
            _state.value = _state.value.copy(status = "Bitte eine http-Stream-URL angeben")
            return
        }
        playStation(url, "Radio")
    }

    fun addFavorite(station: Station) {
        val fav = Favorite(name = station.name, guideId = station.guideId, image = station.image ?: "")
        if (_state.value.favorites.any { it.name == fav.name && it.guideId == fav.guideId }) {
            _state.value = _state.value.copy(status = "„${fav.name}“ ist schon Favorit")
            return
        }
        val next = _state.value.favorites + fav
        favStore.save(next)
        _state.value = _state.value.copy(favorites = next, status = "❤ ${fav.name} gespeichert")
    }

    fun removeFavorite(fav: Favorite) {
        val next = _state.value.favorites.filterNot { it == fav }
        favStore.save(next)
        _state.value = _state.value.copy(favorites = next)
    }

    // ---- Multi-room groups ------------------------------------------------

    /** Create + activate a group from currently known devices, then persist it. */
    fun createGroup(name: String, masterIp: String, memberIps: Set<String>) {
        val devs = _state.value.devices
        val master = devs.firstOrNull { it.ip == masterIp } ?: return
        val slaves = devs.filter { it.ip in memberIps && it.ip != masterIp }
            .map { ZoneMember(it.ip, it.mac) }
        if (slaves.isEmpty()) {
            _state.value = _state.value.copy(status = "Gruppe braucht mindestens 2 Geräte")
            return
        }
        val group = SavedGroup(name.ifBlank { "Gruppe" }, master.ip, master.mac, slaves)
        _state.value = _state.value.copy(status = "Erstelle Gruppe…")
        viewModelScope.launch {
            val ok = SoundTouchClient(master.ip).setZone(master.mac, master.ip, slaves)
            if (ok) {
                val next = _state.value.savedGroups.filterNot { it.name == group.name } + group
                groupStore.save(next)
                _state.value = _state.value.copy(
                    savedGroups = next, selectedGroup = group, selected = master,
                    status = "🔗 Gruppe ${group.name}",
                )
                refreshGroupVolumes(group)
                refresh()
            } else {
                _state.value = _state.value.copy(status = "Gruppe konnte nicht erstellt werden")
            }
        }
    }

    /**
     * Select a group as its own entity: activate the zone and control it as one
     * unit — transport and now-playing via the master, volume across all members.
     * Distinct from selecting an individual speaker.
     */
    fun selectGroup(group: SavedGroup) {
        val master = _state.value.devices.firstOrNull { it.ip == group.masterIp }
            ?: Device(group.name, "Group", group.masterIp, group.masterMac, "")
        _state.value = _state.value.copy(status = "Aktiviere ${group.name}…")
        viewModelScope.launch {
            val ok = SoundTouchClient(group.masterIp)
                .setZone(group.masterMac, group.masterIp, group.slaves)
            if (ok) {
                _state.value = _state.value.copy(
                    selected = master, selectedGroup = group,
                    status = "🔗 Gruppe ${group.name}",
                )
                refreshGroupVolumes(group)
                refresh()
            } else {
                _state.value = _state.value.copy(status = "Aktivierung fehlgeschlagen")
            }
        }
    }

    /** Dissolve the active group (remove every slave). Devices then act standalone. */
    fun dissolveGroup() {
        val group = _state.value.selectedGroup ?: return
        _state.value = _state.value.copy(status = "Löse Gruppe auf…")
        viewModelScope.launch {
            val master = SoundTouchClient(group.masterIp)
            group.slaves.forEach { master.removeZoneSlave(group.masterMac, it.mac) }
            _state.value = _state.value.copy(
                selectedGroup = null, memberVolumes = emptyMap(),
                status = "Gruppe aufgelöst",
            )
        }
    }

    fun deleteGroup(group: SavedGroup) {
        val next = _state.value.savedGroups.filterNot { it.name == group.name }
        groupStore.save(next)
        _state.value = _state.value.copy(
            savedGroups = next,
            selectedGroup = if (_state.value.selectedGroup?.name == group.name) null else _state.value.selectedGroup,
        )
    }

    private fun refreshGroupVolumes(group: SavedGroup) {
        viewModelScope.launch {
            val vols = HashMap<String, Int>()
            group.memberIps.forEach { ip ->
                SoundTouchClient(ip).getVolume()?.actual?.let { vols[ip] = it }
            }
            _state.value = _state.value.copy(memberVolumes = vols)
        }
    }

    /** Change one member's volume directly (relative). */
    fun changeMemberVolume(ip: String, delta: Int) {
        viewModelScope.launch {
            val c = SoundTouchClient(ip)
            val cur = _state.value.memberVolumes[ip] ?: c.getVolume()?.actual
            if (cur == null) {
                _state.value = _state.value.copy(status = "$ip nicht erreichbar (Standby?)")
                return@launch
            }
            val next = (cur + delta).coerceIn(0, 100)
            if (c.setVolume(next)) {
                _state.value = _state.value.copy(
                    memberVolumes = _state.value.memberVolumes + (ip to next),
                )
            }
        }
    }

    /** Change the whole group relatively (preserves the balance between speakers). */
    fun changeGroupVolume(delta: Int) {
        val group = _state.value.selectedGroup ?: return
        group.memberIps.forEach { ip -> changeMemberVolume(ip, delta) }
    }

    /** Volume change that respects the current selection (group vs single device). */
    fun nudgeVolume(delta: Int) {
        if (_state.value.selectedGroup != null) changeGroupVolume(delta) else changeVolume(delta)
    }

    // ---- On-device presets (physical buttons, via SSH) --------------------

    // ---- System audio capture (phone audio to speaker, Phase 5) -----------

    /** Start capturing this phone's audio and stream it to the selected speaker. */
    fun startPhoneStream(resultCode: Int, data: Intent, muteLocal: Boolean) {
        val dev = _state.value.selected ?: return
        val app = getApplication<Application>()
        val svc = Intent(app, AudioCaptureService::class.java).apply {
            action = AudioCaptureService.ACTION_START
            putExtra(AudioCaptureService.EXTRA_RESULT_CODE, resultCode)
            putExtra(AudioCaptureService.EXTRA_RESULT_DATA, data)
            putExtra(AudioCaptureService.EXTRA_BOX_IP, dev.ip)
            putExtra(AudioCaptureService.EXTRA_INIT_VOLUME, _state.value.volume ?: 30)
            val members = _state.value.selectedGroup?.memberIps ?: listOf(dev.ip)
            putStringArrayListExtra(AudioCaptureService.EXTRA_MEMBER_IPS, ArrayList(members))
            putExtra(AudioCaptureService.EXTRA_MUTE_LOCAL, muteLocal)
        }
        app.startForegroundService(svc)

        val ip = Discovery.localIp()
        if (ip == null) {
            _state.value = _state.value.copy(status = "Eigene IP nicht ermittelbar")
            return
        }
        val url = "http://$ip:${AudioCaptureService.PORT}/stream.wav"
        _state.value = _state.value.copy(capturing = true, status = "Starte Audio-Stream…")
        viewModelScope.launch {
            kotlinx.coroutines.delay(800) // let the embedded server bind
            val ok = dlna.playUrl(dev.ip, url, title = "Handy-Audio")
            _state.value = _state.value.copy(
                status = if (ok) "🎧 Streame Handy-Audio" else "Box konnte Stream nicht starten",
            )
        }
    }

    fun stopPhoneStream() {
        val app = getApplication<Application>()
        app.startService(
            Intent(app, AudioCaptureService::class.java).apply { action = AudioCaptureService.ACTION_STOP }
        )
        _state.value = _state.value.copy(capturing = false, status = "Audio-Stream gestoppt")
        client()?.let { c -> viewModelScope.launch { c.sendKey(SoundTouchClient.KEY_STOP) } }
    }

    fun loadPresets(ip: String) {
        viewModelScope.launch {
            val ssh = SshClient(ip)
            if (!ssh.isReachable()) {
                _state.value = _state.value.copy(sshReachable = false, presets = emptyMap())
                return@launch
            }
            _state.value = _state.value.copy(sshReachable = true, presets = ssh.readPresets())
        }
    }

    /** Assign a favorite to a physical preset button (resolves its stream URL first). */
    fun assignPreset(slot: Int, fav: Favorite) {
        val ip = _state.value.selected?.ip ?: return
        _state.value = _state.value.copy(status = "Lege Preset $slot an…")
        viewModelScope.launch {
            val url = tunein.resolveStreamUrl(fav.url.ifBlank { fav.guideId })
            if (url == null) {
                _state.value = _state.value.copy(status = "Stream für ${fav.name} nicht auflösbar")
                return@launch
            }
            val ssh = SshClient(ip)
            if (ssh.setPreset(slot, url, fav.name)) {
                _state.value = _state.value.copy(
                    presets = ssh.readPresets(),
                    status = "🎛 Preset $slot: ${fav.name}",
                )
            } else {
                _state.value = _state.value.copy(status = "Preset $slot fehlgeschlagen (SSH)")
            }
        }
    }

    fun playPreset(preset: Preset) {
        playStation(preset.url, preset.name)
    }

    fun clearPreset(slot: Int) {
        val ip = _state.value.selected?.ip ?: return
        viewModelScope.launch {
            val ssh = SshClient(ip)
            if (ssh.clearPreset(slot)) {
                _state.value = _state.value.copy(
                    presets = ssh.readPresets(), status = "Preset $slot gelöscht",
                )
            }
        }
    }
}