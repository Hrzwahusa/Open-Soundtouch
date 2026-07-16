package com.opensoundtouch

import android.Manifest
import android.app.Activity
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.opensoundtouch.data.Device
import com.opensoundtouch.data.Favorite
import com.opensoundtouch.data.Preset
import com.opensoundtouch.data.SavedGroup
import com.opensoundtouch.data.SoundTouchClient
import com.opensoundtouch.ui.OpenSoundTouchTheme

class MainActivity : ComponentActivity() {

    private val vm: MainViewModel by viewModels()

    // While streaming phone audio, the hardware volume keys control the speaker.
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (vm.state.value.capturing) {
            when (keyCode) {
                KeyEvent.KEYCODE_VOLUME_UP -> { vm.nudgeVolume(+5); return true }
                KeyEvent.KEYCODE_VOLUME_DOWN -> { vm.nudgeVolume(-5); return true }
            }
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent?): Boolean {
        if (vm.state.value.capturing &&
            (keyCode == KeyEvent.KEYCODE_VOLUME_UP || keyCode == KeyEvent.KEYCODE_VOLUME_DOWN)
        ) {
            return true
        }
        return super.onKeyUp(keyCode, event)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            OpenSoundTouchTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    MainScreen(vm)
                }
            }
        }
    }
}

@Composable
fun MainScreen(vm: MainViewModel = viewModel()) {
    val s by vm.state.collectAsState()

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("🔊 Open SoundTouch", fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(12.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Button(onClick = { vm.discover() }, enabled = !s.scanning) {
                Text("🔄 Geräte suchen")
            }
            Spacer(Modifier.width(12.dp))
            if (s.scanning) CircularProgressIndicator(modifier = Modifier.height(20.dp))
            else Text(s.status)
        }

        Spacer(Modifier.height(12.dp))

        if (s.selected == null) {
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                var manualIp by remember { mutableStateOf("") }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = manualIp,
                        onValueChange = { manualIp = it },
                        label = { Text("IP direkt") },
                        placeholder = { Text("192.168.0.178") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    Button(onClick = { vm.addByIp(manualIp) }) { Text("Verbinden") }
                }
                Spacer(Modifier.height(12.dp))

                Text("Geräte:", fontWeight = FontWeight.SemiBold)
                s.devices.forEach { dev ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.weight(1f)) { DeviceRow(dev) { vm.select(dev) } }
                        OutlinedButton(onClick = { vm.forgetDevice(dev) }) { Text("🗑") }
                    }
                }

                Spacer(Modifier.height(16.dp))
                HorizontalDivider()
                Spacer(Modifier.height(12.dp))
                GroupManager(vm, s.devices, s.savedGroups)
            }
        } else {
            var showRadio by remember(s.selected?.ip) { mutableStateOf(false) }
            Box(Modifier.weight(1f)) {
                if (showRadio) RadioScreen(vm) { showRadio = false }
                else ControlPanel(vm) { showRadio = true }
            }
        }
    }
}

@Composable
private fun DeviceRow(dev: Device, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).clickable(onClick = onClick)
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(dev.name, fontWeight = FontWeight.SemiBold)
            Text("${dev.type} · ${dev.ip}", fontSize = 12.sp)
        }
    }
}

@Composable
private fun ControlPanel(vm: MainViewModel, onOpenRadio: () -> Unit) {
    val s by vm.state.collectAsState()
    val dev = s.selected ?: return
    var url by remember { mutableStateOf("") }

    Column(Modifier.verticalScroll(rememberScrollState())) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            Text(
                s.selectedGroup?.let { "🔗 ${it.name}" } ?: dev.name,
                fontWeight = FontWeight.Bold, fontSize = 18.sp,
            )
            OutlinedButton(onClick = { vm.deselect() }) { Text("↩ Geräte") }
        }
        Spacer(Modifier.height(8.dp))

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp)) {
                Text("Now Playing", fontWeight = FontWeight.SemiBold)
                Text(s.nowPlaying?.track ?: "—")
                Text("Status: ${s.nowPlaying?.playStatus ?: "—"}", fontSize = 12.sp)
            }
        }

        Spacer(Modifier.height(12.dp))
        Text("Wiedergabe", fontWeight = FontWeight.SemiBold)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_PREV) }) { Text("⏮") }
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_PLAY_PAUSE) }) { Text("⏯") }
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_STOP) }) { Text("⏹") }
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_NEXT) }) { Text("⏭") }
        }

        Spacer(Modifier.height(12.dp))
        Text("Lautstärke: ${s.volume ?: "—"}", fontWeight = FontWeight.SemiBold)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
            OutlinedButton(onClick = { vm.changeVolume(-5) }) { Text("🔉 −") }
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_POWER) }) { Text("⚡ Power") }
            OutlinedButton(onClick = { vm.changeVolume(+5) }) { Text("🔊 ＋") }
        }

        val group = s.selectedGroup
        if (group != null) {
            GroupVolumeSection(vm, group, s.devices, s.memberVolumes)
        }

        Spacer(Modifier.height(16.dp))
        if (s.selectedGroup == null) {
            var newName by remember(dev.ip) { mutableStateOf(dev.name) }
            Text("Umbenennen", fontWeight = FontWeight.SemiBold)
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = newName, onValueChange = { newName = it },
                    singleLine = true, modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Button(onClick = { vm.renameDevice(newName) }) { Text("OK") }
            }
            Spacer(Modifier.height(16.dp))
        }
        Button(onClick = onOpenRadio, modifier = Modifier.fillMaxWidth()) {
            Text("📻 Internetradio suchen")
        }

        if (s.selectedGroup == null) {
            Spacer(Modifier.height(16.dp))
            PresetSection(vm, dev.ip, s.sshReachable, s.presets, s.favorites)
        }
        CaptureSection(vm, s.capturing)

        Spacer(Modifier.height(16.dp))
        Text("Stream-URL abspielen (DLNA)", fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = url, onValueChange = { url = it },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("http://stream.…/stream.mp3") },
            singleLine = true,
        )
        Spacer(Modifier.height(8.dp))
        Button(onClick = { vm.playUrl(url.trim()) }, modifier = Modifier.fillMaxWidth()) {
            Text("▶️ Abspielen")
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun RadioScreen(vm: MainViewModel, onBack: () -> Unit) {
    val s by vm.state.collectAsState()
    var query by remember { mutableStateOf("") }

    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("📻 Internetradio", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            OutlinedButton(onClick = onBack) { Text("↩ Zurück") }
        }
        Spacer(Modifier.height(8.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = query, onValueChange = { query = it },
                label = { Text("Sender suchen") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            Button(onClick = { vm.search(query) }, enabled = !s.searchBusy) { Text("Suchen") }
        }
        if (s.searchBusy) {
            Spacer(Modifier.height(8.dp))
            CircularProgressIndicator(modifier = Modifier.height(20.dp))
        }
        Spacer(Modifier.height(8.dp))

        LazyColumn(Modifier.weight(1f).fillMaxWidth()) {
            if (s.searchResults.isNotEmpty()) {
                item { Text("Ergebnisse", fontWeight = FontWeight.SemiBold) }
                items(s.searchResults) { st ->
                    StationRow(
                        title = st.name,
                        subtitle = st.subtitle,
                        onPlay = { vm.playStation(st.guideId, st.name) },
                        actionLabel = "❤",
                        onAction = { vm.addFavorite(st) },
                    )
                }
            }
            if (s.favorites.isNotEmpty()) {
                item {
                    Column {
                        Spacer(Modifier.height(12.dp))
                        HorizontalDivider()
                        Spacer(Modifier.height(8.dp))
                        Text("❤ Favoriten", fontWeight = FontWeight.SemiBold)
                    }
                }
                items(s.favorites) { fav ->
                    StationRow(
                        title = fav.name,
                        subtitle = if (fav.guideId.isNotBlank()) "TuneIn" else fav.url,
                        onPlay = { vm.playFavorite(fav) },
                        actionLabel = "🗑",
                        onAction = { vm.removeFavorite(fav) },
                    )
                }
            }
        }
    }
}

@Composable
private fun GroupVolumeSection(
    vm: MainViewModel,
    group: SavedGroup,
    devices: List<Device>,
    volumes: Map<String, Int>,
) {
    Spacer(Modifier.height(16.dp))
    HorizontalDivider()
    Spacer(Modifier.height(8.dp))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically) {
        Text("🔗 Gruppe: ${group.name}", fontWeight = FontWeight.SemiBold)
        OutlinedButton(onClick = { vm.dissolveGroup() }) { Text("Auflösen") }
    }

    Spacer(Modifier.height(8.dp))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically) {
        OutlinedButton(onClick = { vm.changeGroupVolume(-5) }) { Text("🔉 −") }
        Text("Alle (Balance)", fontWeight = FontWeight.SemiBold)
        OutlinedButton(onClick = { vm.changeGroupVolume(+5) }) { Text("🔊 ＋") }
    }

    Spacer(Modifier.height(4.dp))
    Text("Einzeln:", fontSize = 12.sp)
    group.memberIps.forEach { ip ->
        val name = devices.firstOrNull { it.ip == ip }?.name ?: ip
        val isMaster = ip == group.masterIp
        Row(Modifier.fillMaxWidth().padding(vertical = 2.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            Text((if (isMaster) "👑 " else "🔈 ") + name, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { vm.changeMemberVolume(ip, -5) }) { Text("−") }
            Text(volumes[ip]?.toString() ?: "—", modifier = Modifier.padding(horizontal = 8.dp))
            OutlinedButton(onClick = { vm.changeMemberVolume(ip, +5) }) { Text("＋") }
        }
    }
}

@Composable
private fun GroupManager(vm: MainViewModel, devices: List<Device>, savedGroups: List<SavedGroup>) {
    Text("🔗 Multiroom-Gruppen", fontWeight = FontWeight.SemiBold)

    if (savedGroups.isEmpty()) {
        Text("Noch keine Gruppen gespeichert.", fontSize = 12.sp)
    } else {
        savedGroups.forEach { g ->
            Row(Modifier.fillMaxWidth().padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(g.name, fontWeight = FontWeight.SemiBold)
                    Text("${g.memberIps.size} Geräte · Master ${g.masterIp}", fontSize = 11.sp)
                }
                OutlinedButton(onClick = { vm.selectGroup(g) }) { Text("▶") }
                Spacer(Modifier.width(6.dp))
                OutlinedButton(onClick = { vm.deleteGroup(g) }) { Text("🗑") }
            }
        }
    }

    Spacer(Modifier.height(8.dp))
    if (devices.size < 2) {
        Text("Für eine neue Gruppe mindestens 2 Geräte finden bzw. per IP hinzufügen.", fontSize = 12.sp)
    } else {
        var name by remember { mutableStateOf("") }
        var selected by remember { mutableStateOf(setOf<String>()) }
        var masterIp by remember { mutableStateOf<String?>(null) }

        Text("Neue Gruppe:", fontWeight = FontWeight.SemiBold)
        devices.forEach { d ->
            val checked = d.ip in selected
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = checked, onCheckedChange = { chk ->
                    selected = if (chk) selected + d.ip else selected - d.ip
                    if (!chk && masterIp == d.ip) masterIp = null
                    if (chk && masterIp == null) masterIp = d.ip
                })
                Text(d.name, modifier = Modifier.weight(1f))
                if (checked) {
                    OutlinedButton(onClick = { masterIp = d.ip }) {
                        Text(if (masterIp == d.ip) "👑 Master" else "Master?")
                    }
                }
            }
        }
        OutlinedTextField(
            value = name, onValueChange = { name = it },
            label = { Text("Gruppenname") }, singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        Button(
            onClick = {
                masterIp?.let { vm.createGroup(name, it, selected) }
                name = ""; selected = setOf(); masterIp = null
            },
            enabled = selected.size >= 2 && masterIp != null && masterIp in selected,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Gruppe erstellen & aktivieren") }
    }
}

@Composable
private fun CaptureSection(vm: MainViewModel, capturing: Boolean) {
    Spacer(Modifier.height(16.dp))
    HorizontalDivider()
    Spacer(Modifier.height(8.dp))
    Text("🎧 Handy-Audio streamen", fontWeight = FontWeight.SemiBold)

    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
        Text("Benötigt Android 10 oder neuer.", fontSize = 12.sp)
        return
    }

    val context = LocalContext.current
    var muteLocal by remember { mutableStateOf(true) }
    val notifLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }
    val projectionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val data = result.data
        if (result.resultCode == Activity.RESULT_OK && data != null) {
            vm.startPhoneStream(result.resultCode, data, muteLocal)
        }
    }

    Text(
        "Spielt das Audio dieses Handys auf dem Lautsprecher (DRM-geschützte Apps blockieren die Aufnahme evtl.).",
        fontSize = 11.sp,
    )
    Spacer(Modifier.height(8.dp))
    Text(
        "Während des Streamings regeln die Lautstärketasten des Handys die Box/Gruppe (systemweit).",
        fontSize = 11.sp,
    )
    Spacer(Modifier.height(8.dp))
    if (!capturing) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = muteLocal, onCheckedChange = { muteLocal = it })
            Text("Handy-Lautsprecher stummschalten", fontSize = 13.sp)
        }
        Spacer(Modifier.height(4.dp))
        Button(
            onClick = {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
                val mpm = context.getSystemService(MediaProjectionManager::class.java)!!
                projectionLauncher.launch(mpm.createScreenCaptureIntent())
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text("▶️ Streaming starten") }
    } else {
        Button(onClick = { vm.stopPhoneStream() }, modifier = Modifier.fillMaxWidth()) {
            Text("⏹ Streaming stoppen")
        }
    }
}

@Composable
private fun PresetSection(
    vm: MainViewModel,
    ip: String,
    reachable: Boolean?,
    presets: Map<Int, Preset>,
    favorites: List<Favorite>,
) {
    LaunchedEffect(ip) { vm.loadPresets(ip) }

    HorizontalDivider()
    Spacer(Modifier.height(8.dp))
    Text("🎛 Presets (physische Tasten)", fontWeight = FontWeight.SemiBold)

    when (reachable) {
        null -> Text("Prüfe SSH-Verbindung…", fontSize = 12.sp)
        false -> Text("Box per SSH nicht erreichbar — On-Device-Setup nötig.", fontSize = 12.sp)
        true -> {
            (1..6).forEach { n ->
                val p = presets[n]
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 2.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("$n:  ${p?.name ?: "— leer —"}", modifier = Modifier.weight(1f))
                    if (p != null) {
                        OutlinedButton(onClick = { vm.playPreset(p) }) { Text("▶") }
                        Spacer(Modifier.width(6.dp))
                        OutlinedButton(onClick = { vm.clearPreset(n) }) { Text("🗑") }
                    }
                }
            }

            if (favorites.isEmpty()) {
                Text("Erst Favoriten anlegen, dann hier einer Taste zuweisen.", fontSize = 11.sp)
            } else {
                Spacer(Modifier.height(6.dp))
                Text("Favorit einer Taste zuweisen:", fontSize = 12.sp)
                favorites.forEach { fav ->
                    Text(fav.name, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    Row(Modifier.fillMaxWidth().padding(bottom = 4.dp)) {
                        (1..6).forEach { n ->
                            OutlinedButton(
                                onClick = { vm.assignPreset(n, fav) },
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                                modifier = Modifier
                                    .padding(end = 4.dp)
                                    .defaultMinSize(minWidth = 1.dp, minHeight = 32.dp),
                            ) { Text("$n") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StationRow(
    title: String,
    subtitle: String?,
    onPlay: () -> Unit,
    actionLabel: String,
    onAction: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            if (!subtitle.isNullOrBlank()) Text(subtitle, fontSize = 11.sp)
        }
        OutlinedButton(onClick = onPlay) { Text("▶") }
        Spacer(Modifier.width(6.dp))
        OutlinedButton(onClick = onAction) { Text(actionLabel) }
    }
}