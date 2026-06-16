package com.example.ludo

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun LudoScreen(
    modifier: Modifier = Modifier,
) {
    val engine = remember { LudoGameEngine() }
    val scope = rememberCoroutineScope()
    var selectedMode by remember { mutableStateOf(LudoGameMode.Solo) }
    var stake by remember { mutableIntStateOf(500) }
    var matchStarted by remember { mutableStateOf(false) }
    var state by remember { mutableStateOf(engine.newGame(selectedMode)) }
    var displayedDice by remember { mutableIntStateOf(1) }
    var diceSpin by remember { mutableStateOf(0f) }
    var isDiceRolling by remember { mutableStateOf(false) }
    var rollCountdown by remember { mutableIntStateOf(0) }
    var moveCountdown by remember { mutableIntStateOf(0) }
    var isPieceAnimating by remember { mutableStateOf(false) }
    val visualProgressOverrides = remember { mutableStateMapOf<Int, Int>() }
    val visualPointOverrides = remember { mutableStateMapOf<Int, BoardPoint>() }

    suspend fun playDiceRoll(snapshot: LudoUiState, fast: Boolean = false): LudoUiState {
        isDiceRolling = true
        rollCountdown = 0
        moveCountdown = 0
        val steps = if (fast) 8 else 18
        val delayMs = if (fast) 42L else 82L
        repeat(steps) { step ->
            displayedDice = ((displayedDice + step) % 6) + 1
            diceSpin += 42f
            delay(delayMs)
        }
        val rolled = engine.rollDice(snapshot)
        displayedDice = rolled.diceValue ?: displayedDice
        diceSpin += 12f
        delay(if (fast) 160 else 420)
        isDiceRolling = false
        return rolled
    }

    suspend fun rollAndResolve(snapshot: LudoUiState, fast: Boolean = false): LudoUiState {
        val rolled = playDiceRoll(snapshot, fast = fast)
        return if (!rolled.canRoll && rolled.availablePieceIds.isEmpty() && rolled.winner == null) {
            delay(2_000)
            engine.skipTurn(rolled)
        } else {
            rolled
        }
    }

    suspend fun playPieceMove(snapshot: LudoUiState, pieceId: Int): LudoUiState {
        if (isPieceAnimating) return snapshot
        val dice = snapshot.diceValue ?: return snapshot
        val piece = snapshot.pieces.firstOrNull { it.id == pieceId } ?: return snapshot
        val target = engine.targetProgressFor(piece, dice) ?: return snapshot
        val progressSteps = when {
            piece.progress == HOME_PROGRESS -> listOf(FIRST_TRACK_PROGRESS)
            target > piece.progress -> ((piece.progress + 1)..target).toList()
            else -> listOf(target)
        }
        val visualSteps = if (piece.progress == HOME_PROGRESS) {
            listOf(LudoBoardLayout.doorPoint(piece.owner)) +
                progressSteps.map { progress -> LudoBoardLayout.pointFor(piece.owner, progress) }
        } else {
            progressSteps.map { progress -> LudoBoardLayout.pointFor(piece.owner, progress) }
        }

        isPieceAnimating = true
        rollCountdown = 0
        moveCountdown = 0
        visualSteps.forEachIndexed { index, point ->
            visualPointOverrides[pieceId] = point
            delay(if (index == 0 && piece.progress == HOME_PROGRESS) 360 else 300)
        }
        val moved = engine.movePiece(snapshot, pieceId)
        delay(160)
        visualPointOverrides.remove(pieceId)
        visualProgressOverrides.remove(pieceId)
        isPieceAnimating = false
        return moved
    }

    LaunchedEffect(matchStarted, state.currentTurn, state.canRoll, state.availablePieceIds, state.winner) {
        val snapshot = state
        if (matchStarted && snapshot.winner == null && snapshot.currentPlayer.isBot && snapshot.canRoll) {
            delay(120)
            state = rollAndResolve(snapshot, fast = true)
        }
    }

    LaunchedEffect(
        matchStarted,
        state.currentTurn,
        state.canRoll,
        state.availablePieceIds,
        isDiceRolling,
        isPieceAnimating,
        state.winner,
    ) {
        val shouldAutoRoll = matchStarted &&
            state.winner == null &&
            state.canRoll &&
            !state.currentPlayer.isBot &&
            !isDiceRolling &&
            !isPieceAnimating

        if (shouldAutoRoll) {
            moveCountdown = 0
            for (remaining in 5 downTo 1) {
                rollCountdown = remaining
                delay(1_000)
            }
            rollCountdown = 0
            state = rollAndResolve(state)
        } else {
            rollCountdown = 0
        }
    }

    LaunchedEffect(
        matchStarted,
        state.currentTurn,
        state.canRoll,
        state.availablePieceIds,
        isDiceRolling,
        isPieceAnimating,
        state.winner,
    ) {
        val shouldMove = matchStarted &&
            state.winner == null &&
            !state.canRoll &&
            state.availablePieceIds.isNotEmpty() &&
            !isDiceRolling &&
            !isPieceAnimating

        if (shouldMove) {
            rollCountdown = 0
            if (state.currentPlayer.isBot) {
                delay(90)
                val snapshot = state
                val pieceId = engine.chooseBotPiece(snapshot) ?: snapshot.availablePieceIds.minOrNull()
                if (pieceId == null) {
                    state = engine.skipTurn(snapshot)
                } else {
                    scope.launch {
                        state = playPieceMove(snapshot, pieceId)
                    }
                }
            } else {
                for (remaining in 8 downTo 1) {
                    moveCountdown = remaining
                    delay(1_000)
                }
                moveCountdown = 0
                val snapshot = state
                val pieceId = snapshot.availablePieceIds.minOrNull()
                if (pieceId == null) {
                    state = engine.skipTurn(snapshot)
                } else {
                    scope.launch {
                        state = playPieceMove(snapshot, pieceId)
                    }
                }
            }
        } else {
            moveCountdown = 0
        }
    }

    PremiumBackground(modifier = modifier) {
        if (matchStarted) {
            GameTableScreen(
                state = state,
                stake = stake,
                displayedDice = displayedDice,
                diceSpin = diceSpin,
                isDiceRolling = isDiceRolling,
                rollCountdown = rollCountdown,
                moveCountdown = moveCountdown,
                visualProgressOverrides = visualProgressOverrides,
                visualPointOverrides = visualPointOverrides,
                onRollDice = {
                    if (!isDiceRolling && !isPieceAnimating && state.canRoll) {
                        val snapshot = state
                        scope.launch {
                            state = rollAndResolve(snapshot)
                        }
                    }
                },
                onPieceClick = { pieceId ->
                    if (!isDiceRolling && !isPieceAnimating) {
                        val snapshot = state
                        scope.launch {
                            state = playPieceMove(snapshot, pieceId)
                        }
                    }
                },
                onReset = {
                    visualProgressOverrides.clear()
                    visualPointOverrides.clear()
                    rollCountdown = 0
                    moveCountdown = 0
                    state = engine.reset(selectedMode)
                },
                onExit = { matchStarted = false },
            )
        } else {
            MatchLobbyScreen(
                selectedMode = selectedMode,
                stake = stake,
                onModeSelected = { mode ->
                    selectedMode = mode
                    state = engine.reset(mode)
                },
                onStakeChanged = { stake = it.coerceIn(100, 100_000) },
                onStart = {
                    visualProgressOverrides.clear()
                    visualPointOverrides.clear()
                    rollCountdown = 0
                    moveCountdown = 0
                    state = engine.reset(selectedMode)
                    matchStarted = true
                },
            )
        }
    }
}

@Composable
private fun PremiumBackground(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(
                        Color(0xFF170B2E),
                        Color(0xFF090817),
                        Color(0xFF130B22),
                    ),
                ),
            ),
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF5A2EFF).copy(alpha = 0.24f), Color.Transparent),
                    center = Offset(size.width * 0.2f, size.height * 0.06f),
                    radius = size.width * 0.7f,
                ),
                radius = size.width * 0.7f,
                center = Offset(size.width * 0.2f, size.height * 0.06f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF00A3FF).copy(alpha = 0.14f), Color.Transparent),
                    center = Offset(size.width * 0.78f, size.height * 0.88f),
                    radius = size.width * 0.85f,
                ),
                radius = size.width * 0.85f,
                center = Offset(size.width * 0.78f, size.height * 0.88f),
            )
            drawCircle(
                color = Color.White.copy(alpha = 0.09f),
                radius = 2.5.dp.toPx(),
                center = Offset(size.width * 0.14f, size.height * 0.04f),
            )
            drawCircle(
                color = Color.White.copy(alpha = 0.07f),
                radius = 1.6.dp.toPx(),
                center = Offset(size.width * 0.88f, size.height * 0.18f),
            )
            drawCircle(
                color = Color.White.copy(alpha = 0.08f),
                radius = 2.dp.toPx(),
                center = Offset(size.width * 0.32f, size.height * 0.78f),
            )
        }
        content()
    }
}

@Composable
private fun MatchLobbyScreen(
    selectedMode: LudoGameMode,
    stake: Int,
    onModeSelected: (LudoGameMode) -> Unit,
    onStakeChanged: (Int) -> Unit,
    onStart: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 18.dp, vertical = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBadge(text = "×", tint = Color(0xFFFFD061), background = Color(0xFFBA3A46))
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = "لودو ملكية",
                    style = MaterialTheme.typography.headlineMedium,
                    color = Color.White,
                    fontWeight = FontWeight.Black,
                )
                Text(
                    text = "اختر نوع المباراة وابدأ التحدي",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White.copy(alpha = 0.72f),
                )
            }
            IconBadge(text = "⚙", tint = Color.White, background = Color(0x553E496A))
        }

        Spacer(modifier = Modifier.height(28.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            ModeHeroCard(
                title = "4 لاعبين",
                accent = Color(0xFFFFB703),
                selected = selectedMode == LudoGameMode.FourPlayers,
                modifier = Modifier.weight(1f),
                onClick = { onModeSelected(LudoGameMode.FourPlayers) },
            )
            ModeHeroCard(
                title = "1 مقابل 1",
                accent = Color(0xFF1EC8FF),
                selected = selectedMode == LudoGameMode.Solo,
                modifier = Modifier.weight(1f),
                onClick = { onModeSelected(LudoGameMode.Solo) },
            )
        }

        Spacer(modifier = Modifier.height(26.dp))

        GlassPanel {
            Text(
                text = "حدد النمط",
                style = MaterialTheme.typography.titleLarge,
                color = Color.White,
                fontWeight = FontWeight.Black,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(14.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                PremiumOptionButton("السهم", enabled = false, modifier = Modifier.weight(1f))
                PremiumOptionButton("الكلاسيكي", enabled = true, selected = true, modifier = Modifier.weight(1f))
            }
            Spacer(modifier = Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                PremiumOptionButton("الماستر", enabled = false, modifier = Modifier.weight(1f))
                PremiumOptionButton("السريع", enabled = false, modifier = Modifier.weight(1f))
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        GlassPanel {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text("أدوات سحرية", color = Color.White, fontWeight = FontWeight.Bold)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("🎲", style = MaterialTheme.typography.headlineSmall)
                    Box(
                        modifier = Modifier
                            .size(32.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color(0xFF0C233A))
                            .border(1.dp, Color.White.copy(alpha = 0.15f), RoundedCornerShape(8.dp)),
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        GlassPanel {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                IconBadge(text = "+", tint = Color.White, background = Color(0xFFFFC107), onClick = {
                    onStakeChanged(stake + 100)
                })
                Text(
                    text = "$stake 🪙",
                    style = MaterialTheme.typography.headlineSmall,
                    color = Color.White,
                    fontWeight = FontWeight.Black,
                )
                IconBadge(text = "−", tint = Color.White, background = Color(0xFF8C95A7), onClick = {
                    onStakeChanged(stake - 100)
                })
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        Button(
            onClick = onStart,
            modifier = Modifier
                .fillMaxWidth(0.74f)
                .height(58.dp)
                .shadow(14.dp, RoundedCornerShape(18.dp)),
            shape = RoundedCornerShape(18.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD21F)),
        ) {
            Text(
                text = "ابدأ",
                style = MaterialTheme.typography.titleLarge,
                color = Color(0xFF5C3A00),
                fontWeight = FontWeight.Black,
            )
        }
    }
}

@Composable
private fun ModeHeroCard(
    title: String,
    accent: Color,
    selected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val border = if (selected) Color(0xFFFFF176) else Color.White.copy(alpha = 0.14f)
    Box(
        modifier = modifier
            .height(88.dp)
            .shadow(if (selected) 16.dp else 8.dp, RoundedCornerShape(18.dp))
            .clip(RoundedCornerShape(18.dp))
            .background(
                Brush.verticalGradient(
                    listOf(accent.copy(alpha = 0.98f), accent.copy(alpha = 0.58f)),
                ),
            )
            .border(2.dp, border, RoundedCornerShape(18.dp))
            .clickable(onClick = onClick)
            .padding(12.dp),
    ) {
        Text(
            text = title,
            modifier = Modifier.align(Alignment.Center),
            color = Color.White,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Black,
            textAlign = TextAlign.Center,
        )
        AnimatedVisibility(
            visible = selected,
            modifier = Modifier.align(Alignment.TopStart),
        ) {
            Text("✓", color = Color(0xFFFFF176), fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun GlassPanel(content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0x662A7BAA)),
        elevation = CardDefaults.cardElevation(defaultElevation = 10.dp),
        border = BorderStroke(1.dp, Color.White.copy(alpha = 0.12f)),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            content = content,
        )
    }
}

@Composable
private fun PremiumOptionButton(
    label: String,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    selected: Boolean = false,
) {
    val colors = if (selected) {
        listOf(Color(0xFF22B7FF), Color(0xFF1178D6))
    } else {
        listOf(Color(0xFF2D9DDB).copy(alpha = if (enabled) 0.92f else 0.52f), Color(0xFF2371B6).copy(alpha = if (enabled) 0.92f else 0.52f))
    }
    Box(
        modifier = modifier
            .height(46.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(Brush.verticalGradient(colors))
            .border(
                width = if (selected) 2.dp else 1.dp,
                color = if (selected) Color(0xFFFFEB3B) else Color.White.copy(alpha = 0.12f),
                shape = RoundedCornerShape(12.dp),
            ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = Color.White.copy(alpha = if (enabled) 1f else 0.5f),
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun GameTableScreen(
    state: LudoUiState,
    stake: Int,
    displayedDice: Int,
    diceSpin: Float,
    isDiceRolling: Boolean,
    rollCountdown: Int,
    moveCountdown: Int,
    visualProgressOverrides: Map<Int, Int>,
    visualPointOverrides: Map<Int, BoardPoint>,
    onRollDice: () -> Unit,
    onPieceClick: (Int) -> Unit,
    onReset: () -> Unit,
    onExit: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 3.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        GameTopBar(stake = stake, onExit = onExit, onReset = onReset)
        Spacer(modifier = Modifier.height(6.dp))
        TopPlayersRow(
            state = state,
            displayedDice = displayedDice,
            diceSpin = diceSpin,
            isDiceRolling = isDiceRolling,
            rollCountdown = rollCountdown,
            moveCountdown = moveCountdown,
            onRollDice = onRollDice,
        )
        Spacer(modifier = Modifier.height(4.dp))
        LudoBoardStage(
            state = state,
            visualProgressOverrides = visualProgressOverrides,
            visualPointOverrides = visualPointOverrides,
            onPieceClick = onPieceClick,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f, fill = true),
        )
        Spacer(modifier = Modifier.height(4.dp))
        BottomPlayersRow(
            state = state,
            displayedDice = displayedDice,
            diceSpin = diceSpin,
            isDiceRolling = isDiceRolling,
            rollCountdown = rollCountdown,
            moveCountdown = moveCountdown,
            onRollDice = onRollDice,
        )
        Spacer(modifier = Modifier.height(4.dp))
        MoveStatusBar(
            state = state,
            onPieceClick = onPieceClick,
        )
    }
}

@Composable
private fun GameTopBar(
    stake: Int,
    onExit: () -> Unit,
    onReset: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconBadge(text = "🎒", tint = Color.White, background = Color(0xFF1EA0FF), onClick = onExit)
        Surface(
            modifier = Modifier
                .width(168.dp)
                .height(36.dp),
            color = Color(0x77301B46),
            shape = RoundedCornerShape(12.dp),
            border = BorderStroke(1.dp, Color.White.copy(alpha = 0.08f)),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text("$stake", color = Color.White, fontWeight = FontWeight.Black)
                Text("مشاهد", color = Color.White.copy(alpha = 0.75f), style = MaterialTheme.typography.labelMedium)
                Text("👁", color = Color.White)
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            IconBadge(text = "🏆", tint = Color.White, background = Color(0xFFFFB703))
            IconBadge(text = "⚙", tint = Color.White, background = Color(0xFF7E879B), onClick = onReset)
        }
    }
}

@Composable
private fun TopPlayersRow(
    state: LudoUiState,
    displayedDice: Int,
    diceSpin: Float,
    isDiceRolling: Boolean,
    rollCountdown: Int,
    moveCountdown: Int,
    onRollDice: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PlayerSeat(
            state = state,
            player = state.players.first { it.color == LudoPlayerColor.Blue },
            label = "زهور",
            isTurn = state.currentTurn == LudoPlayerColor.Blue,
            alignEnd = false,
            displayedDice = displayedDice,
            diceSpin = diceSpin,
            isDiceRolling = isDiceRolling,
            rollCountdown = rollCountdown,
            moveCountdown = moveCountdown,
            onRollDice = onRollDice,
        )
        PlayerSeat(
            state = state,
            player = state.players.first { it.color == LudoPlayerColor.Red },
            label = "عاشق",
            isTurn = state.currentTurn == LudoPlayerColor.Red,
            alignEnd = true,
            displayedDice = displayedDice,
            diceSpin = diceSpin,
            isDiceRolling = isDiceRolling,
            rollCountdown = rollCountdown,
            moveCountdown = moveCountdown,
            onRollDice = onRollDice,
        )
    }
}

@Composable
private fun BottomPlayersRow(
    state: LudoUiState,
    displayedDice: Int,
    diceSpin: Float,
    isDiceRolling: Boolean,
    rollCountdown: Int,
    moveCountdown: Int,
    onRollDice: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PlayerSeat(
            state = state,
            player = state.players.first { it.color == LudoPlayerColor.Yellow },
            label = "مراجي",
            isTurn = state.currentTurn == LudoPlayerColor.Yellow,
            alignEnd = false,
            displayedDice = displayedDice,
            diceSpin = diceSpin,
            isDiceRolling = isDiceRolling,
            rollCountdown = rollCountdown,
            moveCountdown = moveCountdown,
            onRollDice = onRollDice,
        )
        PlayerSeat(
            state = state,
            player = state.players.first { it.color == LudoPlayerColor.Green },
            label = "Biso Nova",
            isTurn = state.currentTurn == LudoPlayerColor.Green,
            alignEnd = true,
            displayedDice = displayedDice,
            diceSpin = diceSpin,
            isDiceRolling = isDiceRolling,
            rollCountdown = rollCountdown,
            moveCountdown = moveCountdown,
            onRollDice = onRollDice,
        )
    }
}

@Composable
private fun PlayerSeat(
    state: LudoUiState,
    player: LudoPlayer,
    label: String,
    isTurn: Boolean,
    alignEnd: Boolean,
    displayedDice: Int,
    diceSpin: Float,
    isDiceRolling: Boolean,
    rollCountdown: Int,
    moveCountdown: Int,
    onRollDice: () -> Unit,
) {
    val ringColor by animateColorAsState(
        targetValue = if (isTurn) Color(0xFFFFE34D) else player.color.toColor(),
        label = "seat-ring-${player.color}",
    )
    Column(
        horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (alignEnd) {
                SeatDiceTimer(
                    isActive = isTurn,
                    displayedDice = if (isTurn) displayedDice else 1,
                    diceSpin = diceSpin,
                    isDiceRolling = isDiceRolling && isTurn,
                    countdown = if (isTurn) rollCountdown.takeIf { it > 0 } ?: moveCountdown else 0,
                    countdownTotal = if (rollCountdown > 0) 5 else 8,
                    enabled = isTurn && state.canRoll && !state.currentPlayer.isBot && state.winner == null,
                    onClick = onRollDice,
                )
            }
            Box(
                modifier = Modifier
                    .size(if (isTurn) 64.dp else 56.dp)
                    .shadow(if (isTurn) 18.dp else 6.dp, CircleShape)
                    .clip(CircleShape)
                    .background(player.color.toColor().copy(alpha = 0.26f))
                    .border(4.dp, ringColor, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = if (player.isBot) "AI" else label.take(1),
                    color = Color.White,
                    fontWeight = FontWeight.Black,
                )
            }
            if (!alignEnd) {
                SeatDiceTimer(
                    isActive = isTurn,
                    displayedDice = if (isTurn) displayedDice else 1,
                    diceSpin = diceSpin,
                    isDiceRolling = isDiceRolling && isTurn,
                    countdown = if (isTurn) rollCountdown.takeIf { it > 0 } ?: moveCountdown else 0,
                    countdownTotal = if (rollCountdown > 0) 5 else 8,
                    enabled = isTurn && state.canRoll && !state.currentPlayer.isBot && state.winner == null,
                    onClick = onRollDice,
                )
            }
        }
        Text(
            text = label,
            color = Color.White,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun SeatDiceTimer(
    isActive: Boolean,
    displayedDice: Int,
    diceSpin: Float,
    isDiceRolling: Boolean,
    countdown: Int,
    countdownTotal: Int,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val animatedSpin by animateFloatAsState(
        targetValue = if (isDiceRolling) diceSpin else 0f,
        animationSpec = tween(durationMillis = 180, easing = FastOutSlowInEasing),
        label = "seat-dice-spin",
    )
    Box(
        modifier = Modifier
            .size(if (isActive) 76.dp else 44.dp)
            .shadow(if (isActive) 12.dp else 4.dp, RoundedCornerShape(12.dp))
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        DiceFace(
            value = displayedDice,
            active = isActive,
            modifier = Modifier
                .size(if (isActive) 62.dp else 38.dp)
                .graphicsLayer(
                    rotationZ = animatedSpin,
                    translationY = if (isDiceRolling) -5f else 0f,
                    scaleX = if (isDiceRolling) 1.08f else 1f,
                    scaleY = if (isDiceRolling) 1.08f else 1f,
                ),
        )
        if (countdown > 0 && isActive) {
            CountdownClock(
                remaining = countdown,
                total = countdownTotal,
                modifier = Modifier.size(74.dp),
            )
        }
    }
}

@Composable
private fun DiceFace(
    value: Int,
    active: Boolean,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val corner = size.minDimension * 0.22f
        drawRoundRect(
            brush = Brush.linearGradient(
                colors = listOf(
                    Color.White,
                    if (active) Color(0xFFF3F6FF) else Color(0xFFE8EAF2),
                    if (active) Color(0xFFC7CCD8) else Color(0xFFA5AAB8),
                ),
                start = Offset(0f, 0f),
                end = Offset(size.width, size.height),
            ),
            size = size,
            cornerRadius = CornerRadius(corner, corner),
        )
        drawRoundRect(
            color = Color.White.copy(alpha = if (active) 0.86f else 0.56f),
            topLeft = Offset(size.width * 0.1f, size.height * 0.08f),
            size = Size(size.width * 0.45f, size.height * 0.18f),
            cornerRadius = CornerRadius(corner * 0.6f, corner * 0.6f),
        )
        drawRoundRect(
            color = Color.Black.copy(alpha = 0.14f),
            topLeft = Offset(size.width * 0.12f, size.height * 0.82f),
            size = Size(size.width * 0.76f, size.height * 0.08f),
            cornerRadius = CornerRadius(corner * 0.4f, corner * 0.4f),
        )
        drawRoundRect(
            color = if (active) Color(0xFFFFD54F).copy(alpha = 0.55f) else Color.Black.copy(alpha = 0.18f),
            size = size,
            cornerRadius = CornerRadius(corner, corner),
            style = Stroke(width = size.minDimension * 0.045f),
        )

        val pipColor = Color(0xFF111827)
        val pipRadius = size.minDimension * 0.07f
        val left = size.width * 0.29f
        val middle = size.width * 0.5f
        val right = size.width * 0.71f
        val top = size.height * 0.29f
        val center = size.height * 0.5f
        val bottom = size.height * 0.71f

        fun pip(x: Float, y: Float) {
            drawCircle(Color.Black.copy(alpha = 0.12f), pipRadius * 1.28f, Offset(x + pipRadius * 0.16f, y + pipRadius * 0.16f))
            drawCircle(pipColor, pipRadius, Offset(x, y))
            drawCircle(Color.White.copy(alpha = 0.25f), pipRadius * 0.32f, Offset(x - pipRadius * 0.28f, y - pipRadius * 0.28f))
        }

        when (value.coerceIn(1, 6)) {
            1 -> pip(middle, center)
            2 -> {
                pip(left, top)
                pip(right, bottom)
            }
            3 -> {
                pip(left, top)
                pip(middle, center)
                pip(right, bottom)
            }
            4 -> {
                pip(left, top)
                pip(right, top)
                pip(left, bottom)
                pip(right, bottom)
            }
            5 -> {
                pip(left, top)
                pip(right, top)
                pip(middle, center)
                pip(left, bottom)
                pip(right, bottom)
            }
            else -> {
                pip(left, top)
                pip(right, top)
                pip(left, center)
                pip(right, center)
                pip(left, bottom)
                pip(right, bottom)
            }
        }
    }
}

@Composable
private fun CountdownClock(
    remaining: Int,
    total: Int,
    modifier: Modifier = Modifier,
) {
    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val strokeWidth = size.minDimension * 0.09f
            val inset = strokeWidth / 2f + 1.dp.toPx()
            val arcSize = Size(size.width - inset * 2, size.height - inset * 2)
            drawCircle(
                color = Color.Black.copy(alpha = 0.34f),
                radius = size.minDimension * 0.5f,
                center = center,
            )
            drawArc(
                color = Color.White.copy(alpha = 0.24f),
                startAngle = -90f,
                sweepAngle = 360f,
                useCenter = false,
                topLeft = Offset(inset, inset),
                size = arcSize,
                style = Stroke(width = strokeWidth),
            )
            drawArc(
                brush = Brush.sweepGradient(
                    listOf(Color(0xFFFFF176), Color(0xFFFF9F1C), Color(0xFFFFF176)),
                    center = center,
                ),
                startAngle = -90f,
                sweepAngle = 360f * (remaining.toFloat() / total.coerceAtLeast(1)),
                useCenter = false,
                topLeft = Offset(inset, inset),
                size = arcSize,
                style = Stroke(width = strokeWidth),
            )
        }
        Text(
            text = remaining.toString(),
            color = Color.White,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Black,
        )
    }
}

@Composable
private fun LudoBoardStage(
    state: LudoUiState,
    visualProgressOverrides: Map<Int, Int>,
    visualPointOverrides: Map<Int, BoardPoint>,
    onPieceClick: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(1f)
                .shadow(18.dp, RoundedCornerShape(18.dp))
                .clip(RoundedCornerShape(18.dp))
                .background(Brush.verticalGradient(listOf(Color(0xFF8A4E2A), Color(0xFF462B21))))
                .padding(4.dp),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(13.dp))
                    .background(Color(0xFF281D33))
                    .padding(1.dp),
            ) {
                LudoBoard(
                    state = state,
                    visualProgressOverrides = visualProgressOverrides,
                    visualPointOverrides = visualPointOverrides,
                    onPieceClick = onPieceClick,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}

@Composable
private fun LudoBoard(
    state: LudoUiState,
    visualProgressOverrides: Map<Int, Int>,
    visualPointOverrides: Map<Int, BoardPoint>,
    onPieceClick: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    BoxWithConstraints(
        modifier = modifier.aspectRatio(1f),
        contentAlignment = Alignment.Center,
    ) {
        val boardSize = if (maxWidth < maxHeight) maxWidth else maxHeight
        val cellSize = boardSize / BOARD_SIDE_CELLS
        val pieceSize = cellSize * 0.78f
        val visualPieces = state.pieces.map { piece ->
            visualProgressOverrides[piece.id]?.let { progress -> piece.copy(progress = progress) } ?: piece
        }
        val pieceTargets = remember(visualPieces) {
            visualPieces.associate { piece -> piece.id to LudoBoardLayout.cellForPiece(piece) }
        } + visualPointOverrides
        val occupied = pieceTargets.entries.groupBy { it.value.occupancyKey }

        Box(modifier = Modifier.size(boardSize)) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                drawPremiumBoard()
            }

            visualPieces.forEach { piece ->
                val target = pieceTargets.getValue(piece.id)
                val group = occupied.getValue(target.occupancyKey).map { it.key }.sorted()
                val overlap = overlapOffset(group.size, group.indexOf(piece.id))
                val targetX = cellSize * (target.centerX + overlap.first) - pieceSize / 2
                val targetY = cellSize * (target.centerY + overlap.second) - pieceSize / 2
                val animatedX by animateDpAsState(
                    targetValue = targetX,
                    animationSpec = spring(
                        dampingRatio = Spring.DampingRatioMediumBouncy,
                        stiffness = Spring.StiffnessLow,
                    ),
                    label = "piece-${piece.id}-x",
                )
                val animatedY by animateDpAsState(
                    targetValue = targetY,
                    animationSpec = spring(
                        dampingRatio = Spring.DampingRatioMediumBouncy,
                        stiffness = Spring.StiffnessLow,
                    ),
                    label = "piece-${piece.id}-y",
                )
                val canMove = piece.id in state.availablePieceIds && !state.currentPlayer.isBot

                TokenPiece(
                    piece = piece,
                    size = pieceSize,
                    canMove = canMove,
                    modifier = Modifier
                        .offset(x = animatedX, y = animatedY)
                        .zIndex(if (canMove) 2f else 1f)
                        .clickable(enabled = canMove) { onPieceClick(piece.id) },
                )
            }
        }
    }
}

@Composable
private fun TokenPiece(
    piece: LudoPiece,
    size: Dp,
    canMove: Boolean,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .size(size)
            .shadow(if (canMove) 12.dp else 6.dp, CircleShape)
            .clip(CircleShape)
            .background(
                Brush.radialGradient(
                    colors = listOf(
                        Color.White.copy(alpha = 0.92f),
                        piece.owner.toColor().copy(alpha = 0.95f),
                        piece.owner.toColor().copy(alpha = 0.72f),
                    ),
                ),
            )
            .border(
                width = if (canMove) 3.dp else 1.5.dp,
                color = if (canMove) Color(0xFFFFF176) else Color.White.copy(alpha = 0.65f),
                shape = CircleShape,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize(0.58f)
                .clip(CircleShape)
                .background(piece.owner.toColor().copy(alpha = 0.86f)),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = ((piece.id % PIECES_PER_PLAYER) + 1).toString(),
                color = Color.White,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Black,
            )
        }
    }
}

@Composable
private fun MoveStatusBar(
    state: LudoUiState,
    onPieceClick: (Int) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(58.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(Color(0x66302048))
            .border(1.dp, Color.White.copy(alpha = 0.1f), RoundedCornerShape(18.dp))
            .padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = if (state.canRoll) "اضغط النرد بجانب اللاعب الحالي" else "اختر قطعة قبل انتهاء الوقت",
                color = Color.White,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = state.statusMessage,
                color = Color.White.copy(alpha = 0.68f),
                style = MaterialTheme.typography.labelSmall,
            )
        }
        MoveHintBadge(
            state = state,
            onPieceClick = onPieceClick,
        )
    }
}

@Composable
private fun PlayerPulse(color: Color, label: String) {
    Box(
        modifier = Modifier
            .size(58.dp)
            .shadow(16.dp, CircleShape)
            .clip(CircleShape)
            .background(color.copy(alpha = 0.25f))
            .border(4.dp, Color(0xFFFFEC64), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = Color.White, fontWeight = FontWeight.Black)
    }
}

@Composable
private fun DiceButton(
    diceValue: Int?,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(68.dp)
            .shadow(if (enabled) 16.dp else 7.dp, RoundedCornerShape(14.dp))
            .clip(RoundedCornerShape(14.dp))
            .background(
                Brush.verticalGradient(
                    if (enabled) {
                        listOf(Color(0xFFFFDA72), Color(0xFFA65E1D))
                    } else {
                        listOf(Color(0xFF8B8797), Color(0xFF4B4857))
                    },
                ),
            )
            .border(2.dp, Color.White.copy(alpha = 0.38f), RoundedCornerShape(14.dp))
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = diceValue?.toString() ?: "🎲",
            color = Color.White,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Black,
        )
    }
}

@Composable
private fun MoveHintBadge(
    state: LudoUiState,
    onPieceClick: (Int) -> Unit,
) {
    val firstMove = state.availablePieceIds.minOrNull()
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(Color(0xFF24344A))
            .border(3.dp, Color.White.copy(alpha = 0.72f), CircleShape)
            .clickable(enabled = firstMove != null && !state.currentPlayer.isBot) {
                firstMove?.let(onPieceClick)
            },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = firstMove?.let { state.availablePieceIds.size.toString() } ?: "0",
            color = Color.White,
            fontWeight = FontWeight.Black,
        )
    }
}

@Composable
private fun QuickActionsBar() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 18.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        BottomAction(text = "🔇", background = Color(0xFFDADDE6), modifier = Modifier.weight(1f))
        BottomAction(text = "🙂", background = Color(0xFFFFD02E), modifier = Modifier.weight(1f))
        BottomAction(text = "💬", background = Color(0xFFFFC928), badge = "1", modifier = Modifier.weight(1f))
    }
}

@Composable
private fun BottomAction(
    text: String,
    background: Color,
    modifier: Modifier = Modifier,
    badge: String? = null,
) {
    Box(
        modifier = modifier
            .height(42.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(background)
            .border(1.dp, Color.Black.copy(alpha = 0.16f), RoundedCornerShape(14.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = MaterialTheme.typography.titleMedium)
        if (badge != null) {
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = 4.dp, y = (-5).dp)
                    .size(19.dp)
                    .clip(CircleShape)
                    .background(Color(0xFFE63B49)),
                contentAlignment = Alignment.Center,
            ) {
                Text(badge, color = Color.White, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun IconBadge(
    text: String,
    tint: Color,
    background: Color,
    onClick: (() -> Unit)? = null,
) {
    Box(
        modifier = Modifier
            .size(42.dp)
            .shadow(8.dp, RoundedCornerShape(12.dp))
            .clip(RoundedCornerShape(12.dp))
            .background(background)
            .border(1.dp, Color.White.copy(alpha = 0.16f), RoundedCornerShape(12.dp))
            .clickable(enabled = onClick != null) { onClick?.invoke() },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            color = tint,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Black,
        )
    }
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawPremiumBoard() {
    val boardSize = size.minDimension
    val cell = boardSize / BOARD_SIDE_CELLS
    val stroke = 1.dp.toPx()

    drawRoundRect(
        brush = Brush.verticalGradient(listOf(Color(0xFF2B1D32), Color(0xFF171222))),
        size = Size(boardSize, boardSize),
        cornerRadius = CornerRadius(cell * 0.38f),
    )

    LudoBoardLayout.homeBlocks.forEach { block ->
        drawRoundRect(
            brush = Brush.radialGradient(
                colors = listOf(
                    block.color.toColor().copy(alpha = 0.76f),
                    block.color.toColor().copy(alpha = 0.94f),
                    Color.Black.copy(alpha = 0.22f),
                ),
                center = Offset((block.col + 3f) * cell, (block.row + 3f) * cell),
                radius = cell * 4.2f,
            ),
            topLeft = Offset(block.col * cell, block.row * cell),
            size = Size(cell * 6f, cell * 6f),
            cornerRadius = CornerRadius(cell * 0.32f),
        )
        drawCircle(
            color = Color.Black.copy(alpha = 0.12f),
            radius = cell * 2.25f,
            center = Offset((block.col + 3f) * cell, (block.row + 3f) * cell),
        )
    }

    LudoBoardLayout.trackCells.forEachIndexed { index, grid ->
        val safeColor = LudoBoardLayout.safeCellColor(index)?.toColor()?.copy(alpha = 0.45f)
        drawBoardCell(
            col = grid.col,
            row = grid.row,
            cell = cell,
            fill = safeColor ?: Color(0xFFE7E0D4),
            strokeWidth = stroke,
        )
        if (index in LudoBoardLayout.starCells) {
            drawCircle(
                color = Color(0xFF7B7F86).copy(alpha = 0.66f),
                radius = cell * 0.22f,
                center = Offset((grid.col + 0.5f) * cell, (grid.row + 0.5f) * cell),
            )
        }
    }

    LudoBoardLayout.homeLanes.forEach { (color, lane) ->
        lane.forEach { grid ->
            drawBoardCell(
                col = grid.col,
                row = grid.row,
                cell = cell,
                fill = color.toColor().copy(alpha = 0.88f),
                strokeWidth = stroke,
            )
        }
    }

    LudoBoardLayout.homeYards.forEach { (color, cells) ->
        cells.forEach { grid ->
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(Color.White.copy(alpha = 0.46f), color.toColor().copy(alpha = 0.96f)),
                    center = Offset((grid.col + 0.5f) * cell, (grid.row + 0.5f) * cell),
                    radius = cell * 0.46f,
                ),
                radius = cell * 0.45f,
                center = Offset((grid.col + 0.5f) * cell, (grid.row + 0.5f) * cell),
            )
        }
    }

    LudoBoardLayout.doorPoints.forEach { (color, point) ->
        drawRoundRect(
            brush = Brush.verticalGradient(
                listOf(Color.White.copy(alpha = 0.95f), color.toColor().copy(alpha = 0.92f)),
            ),
            topLeft = Offset((point.centerX - 0.36f) * cell, (point.centerY - 0.36f) * cell),
            size = Size(cell * 0.72f, cell * 0.72f),
            cornerRadius = CornerRadius(cell * 0.16f),
        )
        drawRoundRect(
            color = Color.Black.copy(alpha = 0.28f),
            topLeft = Offset((point.centerX - 0.36f) * cell, (point.centerY - 0.36f) * cell),
            size = Size(cell * 0.72f, cell * 0.72f),
            cornerRadius = CornerRadius(cell * 0.16f),
            style = Stroke(cell * 0.04f),
        )
    }

    drawTriangleCenter(cell, LudoPlayerColor.Red.toColor(), top = true)
    drawTriangleCenter(cell, LudoPlayerColor.Blue.toColor(), left = true)
    drawTriangleCenter(cell, LudoPlayerColor.Yellow.toColor(), bottom = true)
    drawTriangleCenter(cell, LudoPlayerColor.Green.toColor(), right = true)
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawBoardCell(
    col: Int,
    row: Int,
    cell: Float,
    fill: Color,
    strokeWidth: Float,
) {
    val inset = cell * 0.035f
    drawRoundRect(
        color = fill,
        topLeft = Offset(col * cell + inset, row * cell + inset),
        size = Size(cell - inset * 2, cell - inset * 2),
        cornerRadius = CornerRadius(cell * 0.08f),
    )
    drawRoundRect(
        color = Color(0xFF1D1D1F).copy(alpha = 0.24f),
        topLeft = Offset(col * cell + inset, row * cell + inset),
        size = Size(cell - inset * 2, cell - inset * 2),
        cornerRadius = CornerRadius(cell * 0.08f),
        style = Stroke(strokeWidth),
    )
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawTriangleCenter(
    cell: Float,
    color: Color,
    top: Boolean = false,
    bottom: Boolean = false,
    left: Boolean = false,
    right: Boolean = false,
) {
    val path = androidx.compose.ui.graphics.Path()
    val center = Offset(cell * 7.5f, cell * 7.5f)
    when {
        top -> {
            path.moveTo(cell * 6f, cell * 6f)
            path.lineTo(cell * 9f, cell * 6f)
            path.lineTo(center.x, center.y)
        }
        bottom -> {
            path.moveTo(cell * 6f, cell * 9f)
            path.lineTo(cell * 9f, cell * 9f)
            path.lineTo(center.x, center.y)
        }
        left -> {
            path.moveTo(cell * 6f, cell * 6f)
            path.lineTo(cell * 6f, cell * 9f)
            path.lineTo(center.x, center.y)
        }
        right -> {
            path.moveTo(cell * 9f, cell * 6f)
            path.lineTo(cell * 9f, cell * 9f)
            path.lineTo(center.x, center.y)
        }
    }
    path.close()
    drawPath(path = path, color = color)
    drawPath(path = path, color = Color.Black.copy(alpha = 0.14f), style = Stroke(cell * 0.035f))
}

private fun overlapOffset(total: Int, index: Int): Pair<Float, Float> {
    if (total <= 1) return 0f to 0f

    val offsets = listOf(
        -0.18f to -0.18f,
        0.18f to -0.18f,
        -0.18f to 0.18f,
        0.18f to 0.18f,
    )
    return offsets[index.coerceIn(0, offsets.lastIndex)]
}

private fun LudoPlayerColor.toColor(): Color = Color(argb)

private data class GridCell(val col: Int, val row: Int)

private data class BoardPoint(
    val centerX: Float,
    val centerY: Float,
) {
    val occupancyKey: String = "${centerX.toInt()}:${centerY.toInt()}"
}

private data class HomeBlock(
    val color: LudoPlayerColor,
    val col: Int,
    val row: Int,
)

private object LudoBoardLayout {
    val trackCells = listOf(
        GridCell(6, 13), GridCell(6, 12), GridCell(6, 11), GridCell(6, 10), GridCell(6, 9),
        GridCell(5, 8), GridCell(4, 8), GridCell(3, 8), GridCell(2, 8), GridCell(1, 8), GridCell(0, 8),
        GridCell(0, 7), GridCell(0, 6), GridCell(1, 6), GridCell(2, 6), GridCell(3, 6), GridCell(4, 6),
        GridCell(5, 6), GridCell(6, 5), GridCell(6, 4), GridCell(6, 3), GridCell(6, 2), GridCell(6, 1),
        GridCell(6, 0), GridCell(7, 0), GridCell(8, 0), GridCell(8, 1), GridCell(8, 2), GridCell(8, 3),
        GridCell(8, 4), GridCell(8, 5), GridCell(9, 6), GridCell(10, 6), GridCell(11, 6), GridCell(12, 6),
        GridCell(13, 6), GridCell(14, 6), GridCell(14, 7), GridCell(14, 8), GridCell(13, 8), GridCell(12, 8),
        GridCell(11, 8), GridCell(10, 8), GridCell(9, 8), GridCell(8, 9), GridCell(8, 10), GridCell(8, 11),
        GridCell(8, 12), GridCell(8, 13), GridCell(8, 14), GridCell(7, 14), GridCell(6, 14),
    )

    val homeLanes = mapOf(
        LudoPlayerColor.Blue to listOf(
            GridCell(1, 7), GridCell(2, 7), GridCell(3, 7), GridCell(4, 7), GridCell(5, 7), GridCell(6, 7),
        ),
        LudoPlayerColor.Red to listOf(
            GridCell(7, 1), GridCell(7, 2), GridCell(7, 3), GridCell(7, 4), GridCell(7, 5), GridCell(7, 6),
        ),
        LudoPlayerColor.Green to listOf(
            GridCell(13, 7), GridCell(12, 7), GridCell(11, 7), GridCell(10, 7), GridCell(9, 7), GridCell(8, 7),
        ),
        LudoPlayerColor.Yellow to listOf(
            GridCell(7, 13), GridCell(7, 12), GridCell(7, 11), GridCell(7, 10), GridCell(7, 9), GridCell(7, 8),
        ),
    )

    val homeYards = mapOf(
        LudoPlayerColor.Blue to listOf(GridCell(2, 2), GridCell(3, 2), GridCell(2, 3), GridCell(3, 3)),
        LudoPlayerColor.Red to listOf(GridCell(11, 2), GridCell(12, 2), GridCell(11, 3), GridCell(12, 3)),
        LudoPlayerColor.Yellow to listOf(GridCell(2, 11), GridCell(3, 11), GridCell(2, 12), GridCell(3, 12)),
        LudoPlayerColor.Green to listOf(GridCell(11, 11), GridCell(12, 11), GridCell(11, 12), GridCell(12, 12)),
    )

    val homeBlocks = listOf(
        HomeBlock(LudoPlayerColor.Blue, 0, 0),
        HomeBlock(LudoPlayerColor.Red, 9, 0),
        HomeBlock(LudoPlayerColor.Yellow, 0, 9),
        HomeBlock(LudoPlayerColor.Green, 9, 9),
    )

    val doorPoints = mapOf(
        LudoPlayerColor.Yellow to BoardPoint(6.5f, 13.5f),
        LudoPlayerColor.Blue to BoardPoint(1.5f, 6.5f),
        LudoPlayerColor.Red to BoardPoint(8.5f, 1.5f),
        LudoPlayerColor.Green to BoardPoint(13.5f, 8.5f),
    )

    val starCells = setOf(2, 8, 15, 21, 28, 34, 41, 47)

    fun doorPoint(color: LudoPlayerColor): BoardPoint =
        doorPoints.getValue(color)

    fun pointFor(owner: LudoPlayerColor, progress: Int): BoardPoint {
        val grid = when {
            progress in FIRST_TRACK_PROGRESS..LAST_TRACK_PROGRESS -> {
                val absoluteIndex = (owner.startCell - progress + trackCells.size) % trackCells.size
                trackCells[absoluteIndex]
            }
            progress >= FIRST_HOME_LANE_PROGRESS -> {
                val laneIndex = (progress - FIRST_HOME_LANE_PROGRESS).coerceIn(0, PIECES_PER_PLAYER + 1)
                homeLanes.getValue(owner)[laneIndex]
            }
            else -> return doorPoint(owner)
        }
        return BoardPoint(
            centerX = grid.col + 0.5f,
            centerY = grid.row + 0.5f,
        )
    }

    fun cellForPiece(piece: LudoPiece): BoardPoint {
        if (piece.progress != HOME_PROGRESS) {
            return pointFor(piece.owner, piece.progress)
        }
        val grid = homeYards.getValue(piece.owner)[piece.id % PIECES_PER_PLAYER]
        return BoardPoint(
            centerX = grid.col + 0.5f,
            centerY = grid.row + 0.5f,
        )
    }

    fun safeCellColor(trackIndex: Int): LudoPlayerColor? =
        LudoPlayerColor.entries.firstOrNull { it.startCell == trackIndex }
}

private const val BOARD_SIDE_CELLS = 15
