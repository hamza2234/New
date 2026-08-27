package com.example.ludo

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.URL

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            NativeLudoTheme {
                Surface(color = MaterialTheme.colorScheme.background) {
                    ProbeScreen()
                }
            }
        }
    }
}

data class ProbeResult(
    val target: String,
    val host: String,
    val ips: String,
    val status: String,
    val elapsedMs: Long,
    val error: String,
) {
    val ok: Boolean = status != "-"

    fun asLine(): String {
        val verdict = if (ok) "OK" else "FAIL"
        return "$verdict | $status | ${elapsedMs}ms | $target | $ips | $error"
    }
}

private val probeTargets = listOf(
    "https://mw-mobileapp.iq.zain.com/",
    "https://cms-mobileapp.iq.zain.com/",
    "https://staging-mobileapp.iq.zain.com/",
    "https://dev-mobileapp.iq.zain.com/",
    "https://qa-mobileapp.iq.zain.com/",
    "http://apitest.startappz.com:5000/gateway/",
    "https://apps.iq.zain.com/mobile",
    "https://apps.iq.zain.com/zain-fi",
    "https://www.iq.zain.com/",
    "https://www.iq.zain.com/ar/imtiyaz",
    "https://www.iq.zain.com/en/imtiyaz",
    "https://www.iq.zain.com/ku/imtiyaz",
    "https://www.iq.zain.com/ar/member-area/topup-myline",
    "https://www.iq.zain.com/en/member-area/topup-myline",
    "https://www.iq.zain.com/ku/member-area/topup-myline",
    "https://www.iq.zain.com/storage/app/media/Registration.mp4",
    "https://www.iq.zain.com/storage/app/media/Forget%20Password.mp4",
    "https://www.iq.zain.com/storage/app/media/Recharge.mp4",
    "https://www.iq.zain.com/storage/app/media/Recharge-credit%20card.mp4",
    "https://www.iq.zain.com/storage/app/media/Offers%20Subscription.mp4",
    "https://zain-mobile-app.firebaseio.com/",
    "https://firebaseinstallations.googleapis.com/",
    "https://firebaseremoteconfig.googleapis.com/",
    "https://firebaseremoteconfigrealtime.googleapis.com/",
    "https://firebase-settings.crashlytics.com/",
    "https://codepush.appcenter.ms/",
    "https://eu-prod.oppwa.com/",
    "https://eu-test.oppwa.com/",
    "https://survey.qualtrics.com/",
    "https://s.qualtrics.com/",
    "https://wa.me/9647802999107",
)

@Composable
fun ProbeScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val results = remember { mutableStateListOf<ProbeResult>() }
    var running by remember { mutableStateOf(false) }
    var networkInfo by remember { mutableStateOf(describeNetwork(context)) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp),
    ) {
        Text("Zain Host Probe", style = MaterialTheme.typography.headlineSmall)
        Text("Turn Wi-Fi off, keep mobile data on, then tap Start.")
        Spacer(Modifier.height(8.dp))
        Text(networkInfo, fontFamily = FontFamily.Monospace)
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                enabled = !running,
                onClick = {
                    running = true
                    results.clear()
                    networkInfo = describeNetwork(context)
                    scope.launch {
                        for (target in probeTargets) {
                            results.add(withContext(Dispatchers.IO) { probe(target) })
                        }
                        running = false
                    }
                },
            ) {
                Text(if (running) "Running..." else "Start Probe")
            }
            Button(
                enabled = results.isNotEmpty(),
                onClick = { copyResults(context, networkInfo, results) },
            ) {
                Text("Copy Results")
            }
        }
        Spacer(Modifier.height(12.dp))
        Text("Reachable: ${results.count { it.ok }}/${probeTargets.size}")
        Spacer(Modifier.height(8.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(results) { result ->
                ProbeResultCard(result)
            }
        }
    }
}

@Composable
private fun ProbeResultCard(result: ProbeResult) {
    val container = if (result.ok) Color(0xFFE8F5E9) else Color(0xFFFFEBEE)
    Card(
        colors = CardDefaults.cardColors(containerColor = container),
        modifier = Modifier.fillMaxWidth(),
    ) {
        SelectionContainer {
            Column(Modifier.padding(10.dp)) {
                Text(result.target, fontFamily = FontFamily.Monospace)
                Text(
                    "${if (result.ok) "OK" else "FAIL"} status=${result.status} time=${result.elapsedMs}ms",
                    fontFamily = FontFamily.Monospace,
                )
                if (result.ips.isNotBlank()) Text("IPs: ${result.ips}", fontFamily = FontFamily.Monospace)
                if (result.error.isNotBlank()) Text("Error: ${result.error}", fontFamily = FontFamily.Monospace)
            }
        }
    }
}

private fun describeNetwork(context: Context): String {
    val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    val network = cm.activeNetwork ?: return "network=none"
    val caps = cm.getNetworkCapabilities(network) ?: return "network=unknown"
    val transports = buildList {
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) add("cellular")
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) add("wifi")
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) add("vpn")
    }
    return "network=${transports.joinToString(",").ifBlank { "other" }}"
}

private fun probe(target: String): ProbeResult {
    val startedAt = System.currentTimeMillis()
    val url = URL(target)
    val host = url.host
    val ips = runCatching {
        InetAddress.getAllByName(host).joinToString(",") { it.hostAddress ?: "" }
    }.getOrDefault("")

    fun request(method: String): Pair<String, String> {
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            instanceFollowRedirects = false
            connectTimeout = 8000
            readTimeout = 8000
            setRequestProperty("User-Agent", "Mozilla/5.0 (Android) zero-rating-probe/1.0")
            setRequestProperty("Accept", "*/*")
            setRequestProperty("Cache-Control", "no-cache")
        }
        return try {
            val code = connection.responseCode
            code.toString() to ""
        } catch (error: Exception) {
            "-" to "${error.javaClass.simpleName}: ${error.message.orEmpty()}"
        } finally {
            connection.disconnect()
        }
    }

    var (status, error) = request("HEAD")
    if (status == "-") {
        val fallback = request("GET")
        status = fallback.first
        error = fallback.second
    }
    return ProbeResult(
        target = target,
        host = host,
        ips = ips,
        status = status,
        elapsedMs = System.currentTimeMillis() - startedAt,
        error = error,
    )
}

private fun copyResults(context: Context, networkInfo: String, results: List<ProbeResult>) {
    val text = buildString {
        appendLine("Zain Host Probe")
        appendLine(networkInfo)
        appendLine("Reachable: ${results.count { it.ok }}/${probeTargets.size}")
        results.forEach { appendLine(it.asLine()) }
    }
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText("zain-host-probe", text))
}

@Composable
fun NativeLudoTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Color(0xFF7851A9),
            secondary = Color(0xFFFF9F1C),
            tertiary = Color(0xFF2EC4B6),
            background = Color(0xFFFFF8F1),
            surface = Color(0xFFFFFFFF),
            onPrimary = Color.White,
            onSecondary = Color(0xFF2D1600),
            onTertiary = Color(0xFF001F1B),
        ),
        content = content,
    )
}

@Preview(showBackground = true, widthDp = 420)
@Composable
private fun LudoScreenPreview() {
    NativeLudoTheme {
        ProbeScreen()
    }
}
