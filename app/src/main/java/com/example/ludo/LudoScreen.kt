package com.example.ludo

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.spring
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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

@Composable
fun LudoScreen(
    modifier: Modifier = Modifier,
) {
    val engine = remember { LudoGameEngine() }
    var selectedMode by remember { mutableStateOf(LudoGameMode.Solo) }
    var stake by remember { mutableIntStateOf(500) }
    var matchStarted by remember { mutableStateOf(false) }
    var state by remember { mutableStateOf(engine.newGame(selectedMode)) }

    LaunchedEffect(matchStarted, state.currentTurn, state.canRoll, state.availablePieceIds, state.winner) {
        val snapshot = state
        if (matchStarted && snapshot.winner == null && snapshot.currentPlayer.isBot) {
            delay(if (snapshot.canRoll) 650 else 450)
            state = if (snapshot.canRoll) {
                engine.rollDice(snapshot)
            } else {
                engine.chooseBotPiece(snapshot)?.let { pieceId ->
                    engine.movePiece(snapshot, pieceId)
                } ?: snapshot
            }
        }
    }

    PremiumBackground(modifier = modifier) {
        if (matchStarted) {
            GameTableScreen(
                state = state,
                stake = stake,
                onRollDice = { state = engine.rollDice(state) },
                onPieceClick = { pieceId -> state = engine.movePiece(state, pieceId) },
                onReset = { state = engine.reset(selectedMode) },
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
                        Color(0xFF301A55),
                        Color(0xFF171331),
                        Color(0xFF221338),
                    ),
                ),
            ),
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF7C4DFF).copy(alpha = 0.34f), Color.Transparent),
                    center = Offset(size.width * 0.2f, size.height * 0.06f),
                    radius = size.width * 0.7f,
                ),
                radius = size.width * 0.7f,
                center = Offset(size.width * 0.2f, size.height * 0.06f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFF00D9FF).copy(alpha = 0.18f), Color.Transparent),
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
    onRollDice: () -> Unit,
    onPieceClick: (Int) -> Unit,
    onReset: () -> Unit,
    onExit: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 8.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        GameTopBar(stake = stake, onExit = onExit, onReset = onReset)
        Spacer(modifier = Modifier.height(12.dp))
        TopPlayersRow(state = state)
        Spacer(modifier = Modifier.height(8.dp))
        LudoBoardStage(
            state = state,
            onPieceClick = onPieceClick,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f, fill = false),
        )
        Spacer(modifier = Modifier.height(8.dp))
        BottomPlayersRow(state = state)
        Spacer(modifier = Modifier.height(8.dp))
        DiceControlBar(
            state = state,
            onRollDice = onRollDice,
            onPieceClick = onPieceClick,
        )
        Spacer(modifier = Modifier.height(10.dp))
        QuickActionsBar()
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
private fun TopPlayersRow(state: LudoUiState) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PlayerSeat(
            player = state.players.first { it.color == LudoPlayerColor.Blue },
            label = "زهور",
            isTurn = state.currentTurn == LudoPlayerColor.Blue,
            alignEnd = false,
        )
        PlayerSeat(
            player = state.players.first { it.color == LudoPlayerColor.Red },
            label = "عاشق",
            isTurn = state.currentTurn == LudoPlayerColor.Red,
            alignEnd = true,
        )
    }
}

@Composable
private fun BottomPlayersRow(state: LudoUiState) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PlayerSeat(
            player = state.players.first { it.color == LudoPlayerColor.Yellow },
            label = "مراجي",
            isTurn = state.currentTurn == LudoPlayerColor.Yellow,
            alignEnd = false,
        )
        PlayerSeat(
            player = state.players.first { it.color == LudoPlayerColor.Green },
            label = "Biso Nova",
            isTurn = state.currentTurn == LudoPlayerColor.Green,
            alignEnd = true,
        )
    }
}

@Composable
private fun PlayerSeat(
    player: LudoPlayer,
    label: String,
    isTurn: Boolean,
    alignEnd: Boolean,
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
            if (alignEnd) SmallGiftBadge()
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
            if (!alignEnd) SmallGiftBadge()
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
private fun SmallGiftBadge() {
    Box(
        modifier = Modifier
            .size(24.dp)
            .clip(CircleShape)
            .background(Brush.verticalGradient(listOf(Color(0xFFFFC857), Color(0xFFFF7A00))))
            .border(1.dp, Color.White.copy(alpha = 0.55f), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text("🎁", style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun LudoBoardStage(
    state: LudoUiState,
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
                .padding(7.dp),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(13.dp))
                    .background(Color(0xFF281D33))
                    .padding(2.dp),
            ) {
                LudoBoard(
                    state = state,
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
        val pieceTargets = remember(state.pieces) {
            state.pieces.associate { piece -> piece.id to LudoBoardLayout.cellForPiece(piece) }
        }
        val occupied = pieceTargets.entries.groupBy { it.value.occupancyKey }

        Box(modifier = Modifier.size(boardSize)) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                drawPremiumBoard()
            }

            state.pieces.forEach { piece ->
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
private fun DiceControlBar(
    state: LudoUiState,
    onRollDice: () -> Unit,
    onPieceClick: (Int) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(78.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        PlayerPulse(color = state.currentTurn.toColor(), label = state.currentTurn.label.take(1))
        Spacer(modifier = Modifier.width(10.dp))
        DiceButton(
            diceValue = state.diceValue,
            enabled = state.canRoll && !state.currentPlayer.isBot && state.winner == null,
            onClick = onRollDice,
        )
        Spacer(modifier = Modifier.width(10.dp))
        MoveHintBadge(
            state = state,
            onPieceClick = onPieceClick,
        )
        Spacer(modifier = Modifier.width(16.dp))
        IconBadge(text = "♛", tint = Color(0xFF4E5871), background = Color(0xFFD7D9E0))
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
        brush = Brush.verticalGradient(listOf(Color(0xFFFFF3DC), Color(0xFFEED2A8))),
        size = Size(boardSize, boardSize),
        cornerRadius = CornerRadius(cell * 0.38f),
    )

    LudoBoardLayout.homeBlocks.forEach { block ->
        drawRoundRect(
            brush = Brush.radialGradient(
                colors = listOf(
                    block.color.toColor().copy(alpha = 0.78f),
                    block.color.toColor(),
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
        val safeColor = LudoBoardLayout.safeCellColor(index)?.toColor()?.copy(alpha = 0.22f)
        drawBoardCell(
            col = grid.col,
            row = grid.row,
            cell = cell,
            fill = safeColor ?: Color(0xFFFDF8EF),
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
                fill = color.toColor().copy(alpha = 0.78f),
                strokeWidth = stroke,
            )
        }
    }

    LudoBoardLayout.homeYards.forEach { (color, cells) ->
        cells.forEach { grid ->
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(Color.White.copy(alpha = 0.55f), color.toColor().copy(alpha = 0.86f)),
                    center = Offset((grid.col + 0.5f) * cell, (grid.row + 0.5f) * cell),
                    radius = cell * 0.46f,
                ),
                radius = cell * 0.45f,
                center = Offset((grid.col + 0.5f) * cell, (grid.row + 0.5f) * cell),
            )
        }
    }

    drawTriangleCenter(cell, LudoPlayerColor.Red.toColor(), top = true)
    drawTriangleCenter(cell, LudoPlayerColor.Green.toColor(), left = true)
    drawTriangleCenter(cell, LudoPlayerColor.Yellow.toColor(), bottom = true)
    drawTriangleCenter(cell, LudoPlayerColor.Blue.toColor(), right = true)
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
        LudoPlayerColor.Red to listOf(
            GridCell(7, 13), GridCell(7, 12), GridCell(7, 11), GridCell(7, 10), GridCell(7, 9), GridCell(7, 8),
        ),
        LudoPlayerColor.Green to listOf(
            GridCell(1, 7), GridCell(2, 7), GridCell(3, 7), GridCell(4, 7), GridCell(5, 7), GridCell(6, 7),
        ),
        LudoPlayerColor.Yellow to listOf(
            GridCell(7, 1), GridCell(7, 2), GridCell(7, 3), GridCell(7, 4), GridCell(7, 5), GridCell(7, 6),
        ),
        LudoPlayerColor.Blue to listOf(
            GridCell(13, 7), GridCell(12, 7), GridCell(11, 7), GridCell(10, 7), GridCell(9, 7), GridCell(8, 7),
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

    val starCells = setOf(2, 8, 15, 21, 28, 34, 41, 47)

    fun cellForPiece(piece: LudoPiece): BoardPoint {
        val grid = when {
            piece.progress == HOME_PROGRESS -> homeYards.getValue(piece.owner)[piece.id % PIECES_PER_PLAYER]
            piece.progress in FIRST_TRACK_PROGRESS..LAST_TRACK_PROGRESS -> {
                val absoluteIndex = (piece.owner.startCell + piece.progress) % trackCells.size
                trackCells[absoluteIndex]
            }
            else -> {
                val laneIndex = (piece.progress - FIRST_HOME_LANE_PROGRESS).coerceIn(0, PIECES_PER_PLAYER + 1)
                homeLanes.getValue(piece.owner)[laneIndex]
            }
        }
        return BoardPoint(
            centerX = grid.col + 0.5f,
            centerY = grid.row + 0.5f,
        )
    }

    fun safeCellColor(trackIndex: Int): LudoPlayerColor? =
        LudoPlayerColor.entries.firstOrNull { it.startCell == trackIndex }
}

private const val BOARD_SIDE_CELLS = 15
