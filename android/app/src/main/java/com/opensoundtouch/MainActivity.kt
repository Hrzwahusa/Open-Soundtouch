package com.opensoundtouch

import android.Manifest
import android.app.Activity
import android.app.LocaleManager
import android.content.Context
import android.media.projection.MediaProjectionManager
import android.os.LocaleList
import android.os.Build
import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatDelegate
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
import androidx.compose.foundation.layout.safeDrawingPadding
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
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.os.LocaleListCompat
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
                    Box(Modifier.safeDrawingPadding()) {
                        MainScreen(vm)
                    }
                }
            }
        }
    }
}

/** Switch the whole app between English and German (recreates the activity). */
private fun setAppLanguage(context: Context, tag: String) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        // Framework per-app locale (API 33+): triggers activity recreation itself.
        context.getSystemService(LocaleManager::class.java)
            ?.applicationLocales = LocaleList.forLanguageTags(tag)
    } else {
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(tag))
    }
}

@Composable
fun MainScreen(vm: MainViewModel = viewModel()) {
    val s by vm.state.collectAsState()

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(stringResource(R.string.app_title), fontSize = 22.sp, fontWeight = FontWeight.Bold)
            val ctx = LocalContext.current
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { setAppLanguage(ctx, "en") }) { Text("EN") }
                TextButton(onClick = { setAppLanguage(ctx, "de") }) { Text("DE") }
            }
        }
        Spacer(Modifier.height(12.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Button(onClick = { vm.discover() }, enabled = !s.scanning) {
                Text(stringResource(R.string.find_devices))
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
                        label = { Text(stringResource(R.string.ip_direct)) },
                        placeholder = { Text("192.168.0.178") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    Button(onClick = { vm.addByIp(manualIp) }) { Text(stringResource(R.string.connect)) }
                }
                Spacer(Modifier.height(12.dp))

                Text(stringResource(R.string.devices_header), fontWeight = FontWeight.SemiBold)
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
                s.selectedGroup?.let { stringResource(R.string.group_prefix, it.name) } ?: dev.name,
                fontWeight = FontWeight.Bold, fontSize = 18.sp,
            )
            OutlinedButton(onClick = { vm.deselect() }) { Text(stringResource(R.string.back_devices)) }
        }
        Spacer(Modifier.height(8.dp))

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp)) {
                Text(stringResource(R.string.now_playing), fontWeight = FontWeight.SemiBold)
                Text(s.nowPlaying?.track ?: "—")
                Text(stringResource(R.string.status_fmt, s.nowPlaying?.playStatus ?: "—"), fontSize = 12.sp)
            }
        }

        Spacer(Modifier.height(12.dp))
        Text(stringResource(R.string.playback), fontWeight = FontWeight.SemiBold)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_PREV) }) { Text("⏮") }
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_PLAY_PAUSE) }) { Text("⏯") }
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_STOP) }) { Text("⏹") }
            OutlinedButton(onClick = { vm.sendKey(SoundTouchClient.KEY_NEXT) }) { Text("⏭") }
        }

        Spacer(Modifier.height(12.dp))
        Text(stringResource(R.string.volume_fmt, s.volume?.toString() ?: "—"), fontWeight = FontWeight.SemiBold)
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
            Text(stringResource(R.string.rename), fontWeight = FontWeight.SemiBold)
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
            Text(stringResource(R.string.open_radio))
        }

        if (s.selectedGroup == null) {
            Spacer(Modifier.height(16.dp))
            PresetSection(vm, dev.ip, s.sshReachable, s.presets, s.favorites)
        }
        CaptureSection(vm, s.capturing)

        Spacer(Modifier.height(16.dp))
        Text(stringResource(R.string.stream_url_title), fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = url, onValueChange = { url = it },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("http://stream.…/stream.mp3") },
            singleLine = true,
        )
        Spacer(Modifier.height(8.dp))
        Button(onClick = { vm.playUrl(url.trim()) }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.play))
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
            Text(stringResource(R.string.radio_title), fontWeight = FontWeight.Bold, fontSize = 18.sp)
            OutlinedButton(onClick = onBack) { Text(stringResource(R.string.back)) }
        }
        Spacer(Modifier.height(8.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = query, onValueChange = { query = it },
                label = { Text(stringResource(R.string.search_stations)) },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            Button(onClick = { vm.search(query) }, enabled = !s.searchBusy) { Text(stringResource(R.string.search)) }
        }
        if (s.searchBusy) {
            Spacer(Modifier.height(8.dp))
            CircularProgressIndicator(modifier = Modifier.height(20.dp))
        }
        Spacer(Modifier.height(8.dp))

        val tunein = stringResource(R.string.source_tunein)
        LazyColumn(Modifier.weight(1f).fillMaxWidth()) {
            if (s.searchResults.isNotEmpty()) {
                item { Text(stringResource(R.string.results), fontWeight = FontWeight.SemiBold) }
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
                        Text(stringResource(R.string.favorites_header), fontWeight = FontWeight.SemiBold)
                    }
                }
                items(s.favorites) { fav ->
                    StationRow(
                        title = fav.name,
                        subtitle = if (fav.guideId.isNotBlank()) tunein else fav.url,
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
        Text(stringResource(R.string.group_label, group.name), fontWeight = FontWeight.SemiBold)
        OutlinedButton(onClick = { vm.dissolveGroup() }) { Text(stringResource(R.string.dissolve)) }
    }

    Spacer(Modifier.height(8.dp))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically) {
        OutlinedButton(onClick = { vm.changeGroupVolume(-5) }) { Text("🔉 −") }
        Text(stringResource(R.string.all_balance), fontWeight = FontWeight.SemiBold)
        OutlinedButton(onClick = { vm.changeGroupVolume(+5) }) { Text("🔊 ＋") }
    }

    Spacer(Modifier.height(4.dp))
    Text(stringResource(R.string.individual), fontSize = 12.sp)
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
    Text(stringResource(R.string.groups_title), fontWeight = FontWeight.SemiBold)

    if (savedGroups.isEmpty()) {
        Text(stringResource(R.string.no_groups_saved), fontSize = 12.sp)
    } else {
        savedGroups.forEach { g ->
            Row(Modifier.fillMaxWidth().padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(g.name, fontWeight = FontWeight.SemiBold)
                    Text(stringResource(R.string.group_members, g.memberIps.size, g.masterIp), fontSize = 11.sp)
                }
                OutlinedButton(onClick = { vm.selectGroup(g) }) { Text("▶") }
                Spacer(Modifier.width(6.dp))
                OutlinedButton(onClick = { vm.deleteGroup(g) }) { Text("🗑") }
            }
        }
    }

    Spacer(Modifier.height(8.dp))
    if (devices.size < 2) {
        Text(stringResource(R.string.need_two_devices), fontSize = 12.sp)
    } else {
        var name by remember { mutableStateOf("") }
        var selected by remember { mutableStateOf(setOf<String>()) }
        var masterIp by remember { mutableStateOf<String?>(null) }

        Text(stringResource(R.string.new_group), fontWeight = FontWeight.SemiBold)
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
                        Text(if (masterIp == d.ip) stringResource(R.string.master_yes) else stringResource(R.string.master_ask))
                    }
                }
            }
        }
        OutlinedTextField(
            value = name, onValueChange = { name = it },
            label = { Text(stringResource(R.string.group_name)) }, singleLine = true,
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
        ) { Text(stringResource(R.string.create_group)) }
    }
}

@Composable
private fun CaptureSection(vm: MainViewModel, capturing: Boolean) {
    Spacer(Modifier.height(16.dp))
    HorizontalDivider()
    Spacer(Modifier.height(8.dp))
    Text(stringResource(R.string.capture_title), fontWeight = FontWeight.SemiBold)

    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
        Text(stringResource(R.string.needs_android10), fontSize = 12.sp)
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

    Text(stringResource(R.string.capture_desc), fontSize = 11.sp)
    Spacer(Modifier.height(8.dp))
    Text(stringResource(R.string.capture_keys_hint), fontSize = 11.sp)
    Spacer(Modifier.height(8.dp))
    if (!capturing) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = muteLocal, onCheckedChange = { muteLocal = it })
            Text(stringResource(R.string.mute_phone), fontSize = 13.sp)
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
        ) { Text(stringResource(R.string.start_streaming)) }
    } else {
        Button(onClick = { vm.stopPhoneStream() }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.stop_streaming))
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
    Text(stringResource(R.string.presets_title), fontWeight = FontWeight.SemiBold)

    when (reachable) {
        null -> Text(stringResource(R.string.checking_ssh), fontSize = 12.sp)
        false -> Text(stringResource(R.string.ssh_unreachable), fontSize = 12.sp)
        true -> {
            val empty = stringResource(R.string.empty_slot)
            (1..6).forEach { n ->
                val p = presets[n]
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 2.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("$n:  ${p?.name ?: empty}", modifier = Modifier.weight(1f))
                    if (p != null) {
                        OutlinedButton(onClick = { vm.playPreset(p) }) { Text("▶") }
                        Spacer(Modifier.width(6.dp))
                        OutlinedButton(onClick = { vm.clearPreset(n) }) { Text("🗑") }
                    }
                }
            }

            if (favorites.isEmpty()) {
                Text(stringResource(R.string.no_favorites_hint), fontSize = 11.sp)
            } else {
                Spacer(Modifier.height(6.dp))
                Text(stringResource(R.string.assign_favorite), fontSize = 12.sp)
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
