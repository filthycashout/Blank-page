from pathlib import Path

root = Path("extracted/EntertainmentHubTV")

def must_replace(path, old, new, count=None):
    p = root / path
    s = p.read_text()
    if old not in s:
        raise RuntimeError(f"Patch anchor missing in {path}: {old[:80]!r}")
    p.write_text(s.replace(old, new) if count is None else s.replace(old, new, count))

must_replace(
    "app/src/main/java/com/filthycashout/entertainment/data/Models.kt",
    "enum class SourceType { DEMO, M3U, XTREAM_LIVE, XTREAM_VOD }",
    "enum class SourceType { FREE_LIBRARY, DEMO, M3U, XTREAM_LIVE, XTREAM_VOD }",
)

must_replace(
    "app/src/main/java/com/filthycashout/entertainment/data/SecurePrefs.kt",
    '''    private fun defaultProfile(slot: Int): SourceProfile = when (slot) {
        0 -> SourceProfile(slot, "Demo Stream", SourceType.DEMO)
        1 -> SourceProfile(slot, "Live M3U", SourceType.M3U)
        2 -> SourceProfile(slot, "Xtream Live", SourceType.XTREAM_LIVE)
        3 -> SourceProfile(slot, "Backup Live", SourceType.XTREAM_LIVE)
        4 -> SourceProfile(slot, "Xtream VOD", SourceType.XTREAM_VOD)
        else -> SourceProfile(slot, "My Playlist", SourceType.M3U)
    }''',
    '''    private fun defaultProfile(slot: Int): SourceProfile = when (slot) {
        0 -> SourceProfile(slot, "Free & Legal", SourceType.FREE_LIBRARY)
        1 -> SourceProfile(slot, "Demo Lab", SourceType.DEMO)
        2 -> SourceProfile(slot, "Live M3U", SourceType.M3U)
        3 -> SourceProfile(slot, "Xtream Live", SourceType.XTREAM_LIVE)
        4 -> SourceProfile(slot, "Xtream VOD", SourceType.XTREAM_VOD)
        else -> SourceProfile(slot, "My Playlist", SourceType.M3U)
    }''',
)

portal_path = "app/src/main/java/com/filthycashout/entertainment/data/PortalClient.kt"
p = root / portal_path
s = p.read_text()
s = s.replace(
    '''    suspend fun load(profile: SourceProfile): List<StreamItem> = when (profile.type) {
        SourceType.DEMO -> demoItems(profile.slot)''',
    '''    suspend fun load(profile: SourceProfile): List<StreamItem> = when (profile.type) {
        SourceType.FREE_LIBRARY -> freeLibraryItems(profile.slot)
        SourceType.DEMO -> demoItems(profile.slot)''',
)
s = s.replace(
    '''            val url = when (profile.type) {
                SourceType.DEMO -> DEMO_URL''',
    '''            val url = when (profile.type) {
                SourceType.FREE_LIBRARY -> FREE_LIBRARY_HEALTH_URL
                SourceType.DEMO -> DEMO_URL''',
)
marker = "    fun suggestedEpgUrl(profile: SourceProfile): String? {"
if marker not in s:
    raise RuntimeError("PortalClient EPG marker missing")
s = s.replace(marker, '''    fun builtInEpg(profile: SourceProfile, items: List<StreamItem>): Map<String, List<EpgProgram>> {
        if (profile.type != SourceType.FREE_LIBRARY && profile.type != SourceType.DEMO) return emptyMap()
        val now = System.currentTimeMillis()
        val slotMs = 30L * 60L * 1000L
        val aligned = now - (now % slotMs)
        return items.filter { it.kind == StreamKind.LIVE }.associate { item ->
            val id = item.tvgId ?: item.id
            id to listOf(
                EpgProgram(id, "Live test window", "Built-in no-login playback validation.", aligned, aligned + slotMs),
                EpgProgram(id, "Adaptive playback lab", "Use audio, subtitle, quality, speed, aspect and PiP controls.", aligned + slotMs, aligned + 2 * slotMs),
                EpgProgram(id, "Source health check", "Built-in public test feed monitoring.", aligned + 2 * slotMs, aligned + 3 * slotMs)
            )
        }
    }

''' + marker, 1)

demo_marker = "    private fun demoItems(slot: Int): List<StreamItem> = listOf("
if demo_marker not in s:
    raise RuntimeError("PortalClient demo marker missing")
s = s.replace(demo_marker, '''    private fun freeLibraryItems(slot: Int): List<StreamItem> = listOf(
        StreamItem(
            id = "free-bbb-hls",
            name = "Big Buck Bunny • HLS",
            url = DEMO_URL,
            group = "Free & Legal • Movies",
            kind = StreamKind.VOD,
            description = "Public developer test stream used to validate HLS playback, seeking, resume, favorites and PiP.",
            sourceSlot = slot
        ),
        StreamItem(
            id = "free-tears-dash",
            name = "Tears of Steel • DASH",
            url = DASH_DEMO_URL,
            group = "Free & Legal • Movies",
            kind = StreamKind.VOD,
            description = "Clear DASH developer test asset for adaptive playback and quality selection.",
            sourceSlot = slot
        ),
        StreamItem(
            id = "free-apple-advanced",
            name = "Apple Advanced HLS",
            url = APPLE_ADVANCED_HLS_URL,
            group = "Free & Legal • Showcase",
            kind = StreamKind.VOD,
            description = "Apple HLS example stream for testing advanced tracks and adaptive playback.",
            sourceSlot = slot
        ),
        StreamItem(
            id = "free-live-lab",
            name = "Low-Latency Live Lab",
            url = APPLE_LL_HLS_URL,
            group = "Free & Legal • Live Lab",
            kind = StreamKind.LIVE,
            tvgId = "free-live-lab",
            description = "Public low-latency HLS test feed. Availability can vary because it is a developer test endpoint.",
            sourceSlot = slot
        )
    )

''' + demo_marker, 1)

s = s.replace('url = "https://storage.googleapis.com/wvmedia/clear/h264/tears/tears.mpd"', "url = DASH_DEMO_URL")
s = s.replace(
    '''        const val DEMO_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
        const val USER_AGENT = "EntertainmentHubTV/2.0"''',
    '''        const val DEMO_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
        const val DASH_DEMO_URL = "https://storage.googleapis.com/wvmedia/clear/h264/tears/tears.mpd"
        const val APPLE_ADVANCED_HLS_URL = "https://devstreaming-cdn.apple.com/videos/streaming/examples/adv_dv_atmos/main.m3u8"
        const val APPLE_LL_HLS_URL = "https://ll-hls-test.cdn-apple.com/llhls4/ll-hls-test-04/multi.m3u8"
        const val FREE_LIBRARY_HEALTH_URL = DEMO_URL
        const val USER_AGENT = "EntertainmentHubTV/3.0"''',
)
p.write_text(s)

app_path = "app/src/main/java/com/filthycashout/entertainment/ui/App.kt"
p = root / app_path
s = p.read_text()
s = s.replace(
    '''                    streams = items
                    screen = Screen.LIST
                    loading = false
                    val epgUrl = client.suggestedEpgUrl(profile)''',
    '''                    streams = items
                    screen = Screen.LIST
                    loading = false
                    val builtInGuide = client.builtInEpg(profile, items)
                    if (builtInGuide.isNotEmpty()) epg = builtInGuide
                    val epgUrl = client.suggestedEpgUrl(profile)''',
)
s = s.replace(
    'Text("Live TV, VOD, guide, favorites and resume playback.", fontSize = 17.sp, color = Color.LightGray)',
    'Text("No account required for the built-in library. Live TV, VOD, guide, favorites and resume playback.", fontSize = 17.sp, color = Color.LightGray)',
)
s = s.replace(
    "if (current.type != SourceType.DEMO) {",
    "if (current.type != SourceType.DEMO && current.type != SourceType.FREE_LIBRARY) {",
)
s = s.replace(
    '''private fun SourceProfile.isConfigured(): Boolean = when (type) {
    SourceType.DEMO -> true''',
    '''private fun SourceProfile.isConfigured(): Boolean = when (type) {
    SourceType.FREE_LIBRARY, SourceType.DEMO -> true''',
)
s = s.replace(
    '''private fun SourceType.prettyName(): String = when (this) {
    SourceType.DEMO -> "Demo"''',
    '''private fun SourceType.prettyName(): String = when (this) {
    SourceType.FREE_LIBRARY -> "Built-in free library"
    SourceType.DEMO -> "Demo"''',
)
p.write_text(s)

player_path = "app/src/main/java/com/filthycashout/entertainment/player/PlayerScreen.kt"
p = root / player_path
s = p.read_text()
s = s.replace("import android.widget.FrameLayout", "import android.widget.FrameLayout\nimport androidx.media3.ui.AspectRatioFrameLayout")
s = s.replace(
    "import androidx.compose.material3.Button",
    "import androidx.compose.material3.Button\nimport androidx.compose.material3.DropdownMenu\nimport androidx.compose.material3.DropdownMenuItem",
)
s = s.replace(
    '''    var showTracks by remember { mutableStateOf(false) }
    var tracksVersion by remember { mutableIntStateOf(0) }''',
    '''    var showTracks by remember { mutableStateOf(false) }
    var speedExpanded by remember { mutableStateOf(false) }
    var playbackSpeed by remember { mutableStateOf(1f) }
    var resizeMode by remember { mutableIntStateOf(AspectRatioFrameLayout.RESIZE_MODE_FIT) }
    var tracksVersion by remember { mutableIntStateOf(0) }''',
)
s = s.replace(
    '''                    controllerHideOnTouch = true
                    layoutParams = FrameLayout.LayoutParams(''',
    '''                    controllerHideOnTouch = true
                    this.resizeMode = resizeMode
                    layoutParams = FrameLayout.LayoutParams(''',
)
s = s.replace(
    "            update = { it.player = player }",
    '''            update = {
                it.player = player
                it.resizeMode = resizeMode
            }''',
)
s = s.replace(
    '''            Button(onClick = { showTracks = true }) { Text("Audio / Subtitles") }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {''',
    '''            Button(onClick = { showTracks = true }) { Text("Tracks / Quality") }
            Box {
                Button(onClick = { speedExpanded = true }) { Text("\${playbackSpeed}x") }
                DropdownMenu(expanded = speedExpanded, onDismissRequest = { speedExpanded = false }) {
                    listOf(0.5f, 0.75f, 1f, 1.25f, 1.5f, 2f).forEach { speed ->
                        DropdownMenuItem(
                            text = { Text("\${speed}x") },
                            onClick = {
                                playbackSpeed = speed
                                player.setPlaybackSpeed(speed)
                                speedExpanded = false
                            }
                        )
                    }
                }
            }
            Button(onClick = {
                resizeMode = when (resizeMode) {
                    AspectRatioFrameLayout.RESIZE_MODE_FIT -> AspectRatioFrameLayout.RESIZE_MODE_ZOOM
                    AspectRatioFrameLayout.RESIZE_MODE_ZOOM -> AspectRatioFrameLayout.RESIZE_MODE_FILL
                    else -> AspectRatioFrameLayout.RESIZE_MODE_FIT
                }
            }) {
                Text(
                    when (resizeMode) {
                        AspectRatioFrameLayout.RESIZE_MODE_ZOOM -> "Zoom"
                        AspectRatioFrameLayout.RESIZE_MODE_FILL -> "Fill"
                        else -> "Fit"
                    }
                )
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {''',
)
s = s.replace(
    '''            onSelect = { option ->
                val builder = player.trackSelectionParameters.buildUpon()
                    .clearOverridesOfType(option.type)
                    .setTrackTypeDisabled(option.type, false)
                builder.addOverride(TrackSelectionOverride(option.group.mediaTrackGroup, listOf(option.trackIndex)))
                player.trackSelectionParameters = builder.build()
                showTracks = false
            },''',
    '''            onSelect = { option ->
                val builder = player.trackSelectionParameters.buildUpon()
                    .clearOverridesOfType(option.type)
                    .setTrackTypeDisabled(option.type, false)
                if (option.trackIndex >= 0) {
                    builder.addOverride(TrackSelectionOverride(option.group.mediaTrackGroup, listOf(option.trackIndex)))
                }
                player.trackSelectionParameters = builder.build()
                showTracks = false
            },''',
)
s = s.replace('title = { Text("Audio & subtitle tracks") },', 'title = { Text("Tracks & quality") },')
s = s.replace(
    '''                if (options.any { it.type == C.TRACK_TYPE_TEXT }) {''',
    '''                if (options.any { it.type == C.TRACK_TYPE_VIDEO }) {
                    item {
                        TextButton(onClick = {
                            val video = options.first { it.type == C.TRACK_TYPE_VIDEO }
                            onSelect(video.copy(trackIndex = -1, label = "Video • Auto", selected = false))
                        }) { Text("Video quality: Auto") }
                    }
                }
                if (options.any { it.type == C.TRACK_TYPE_TEXT }) {''',
    1,
)
s = s.replace(
    "        if (group.type != C.TRACK_TYPE_AUDIO && group.type != C.TRACK_TYPE_TEXT) return@forEach",
    "        if (group.type != C.TRACK_TYPE_VIDEO && group.type != C.TRACK_TYPE_AUDIO && group.type != C.TRACK_TYPE_TEXT) return@forEach",
)
s = s.replace(
    '''            val kind = if (group.type == C.TRACK_TYPE_AUDIO) "Audio" else "Subtitle"
            val name = format.label?.takeIf { it.isNotBlank() }
                ?: format.language?.takeIf { it.isNotBlank() }
                ?: "Track \${i + 1}"''',
    '''            val kind = when (group.type) {
                C.TRACK_TYPE_VIDEO -> "Video"
                C.TRACK_TYPE_AUDIO -> "Audio"
                else -> "Subtitle"
            }
            val videoLabel = if (group.type == C.TRACK_TYPE_VIDEO) {
                val height = format.height.takeIf { it > 0 }?.let { "\${it}p" }
                val bitrate = format.bitrate.takeIf { it > 0 }?.let { "\${it / 1000} kbps" }
                listOfNotNull(height, bitrate).joinToString(" • ").ifBlank { null }
            } else null
            val name = videoLabel
                ?: format.label?.takeIf { it.isNotBlank() }
                ?: format.language?.takeIf { it.isNotBlank() }
                ?: "Track \${i + 1}"''',
)
p.write_text(s)

gradle = root / "app/build.gradle.kts"
s = gradle.read_text().replace("versionCode = 2", "versionCode = 3").replace('versionName = "2.0.0"', 'versionName = "3.0.0"')
gradle.write_text(s)

(root / "README.md").write_text("""# Entertainment Hub TV 3.0

Android TV / NVIDIA Shield all-in-one media client with a no-account built-in free/test library plus optional user-owned sources.

Built in: Free & Legal catalog, Demo Lab, generated guide, search/categories, favorites, recent items, continue watching, health checks, audio/subtitle/video-quality selection, speed, Fit/Zoom/Fill and PiP.

Optional: M3U/M3U8, XMLTV, authorized Xtream-style Live/VOD, and ScrapeGraphAI metadata enrichment from public/authorized pages.

The project intentionally contains no hidden-stream extraction, copied browser cookies, DRM-key acquisition, paywall bypass, or bundled pirate stream directory.
""")

assert "FREE_LIBRARY" in (root / "app/src/main/java/com/filthycashout/entertainment/data/Models.kt").read_text()
assert 'versionName = "3.0.0"' in gradle.read_text()
assert "Tracks / Quality" in p.read_text()
print("Entertainment Hub TV v3 patch applied")
