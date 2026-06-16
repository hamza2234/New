package com.example.ludo

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.matchParentSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import kotlinx.coroutines.delay

@Composable
fun LudoScreen(
    modifier: Modifier = Modifier,
) {
    val engine = remember { LudoGameEngine() }
    var selectedMode by remember { mutableStateOf(LudoGameMode.Solo) }
    var state by remember { mutableStateOf(engine.newGame(selectedMode)) }

    LaunchedEffect(state.currentTurn, state.canRoll, state.availablePieceIds, state.winner) {
        val snapshot = state
        if (snapshot.winner == null && snapshot.currentPlayer.isBot) {
            delay(if (snapshot.canRoll) 650 else 420)
            state = if (snapshot.canRoll) {
                engine.rollDice(snapshot)
            } else {
                engine.chooseBotPiece(snapshot)?.let { pieceId ->
                    engine.movePiece(snapshot, pieceId)
                } ?: snapshot
            }
        }
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        Color(0xFFFFF8F1),
                        Color(0xFFFFEDD5),
                        Color(0xFFF6E7FF),
                    ),
                ),
            ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            LudoHeader()
            GameModeSelector(
                selectedMode = selectedMode,
                onModeSelected = { mode ->
                    selectedMode = mode
                    state = engine.reset(mode)
                },
            )
            TurnPanel(
                state = state,
                onRollDice = { state = engine.rollDice(state) },
                onReset = { state = engine.reset(selectedMode) },
            )
            LudoBoardCard(
                state = state,
                onPieceClick = { pieceId -> state = engine.movePiece(state, pieceId) },
            )
            AvailableMoves(
                state = state,
                onPieceClick = { pieceId -> state = engine.movePiece(state, pieceId) },
            )
            PlayerSummaryGrid(state = state)
            Spacer(modifier = Modifier.height(18.dp))
        }
    }
}

@Composable
private fun LudoHeader() {
    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(containerColor = Color.White.copy(alpha = 0.88f)),
        shape = RoundedCornerShape(28.dp),
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = "لعبة لودو نيتف",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Black,
                color = Color(0xFF33214F),
            )
            Text(
                text = "واجهة Compose جاهزة للربط لاحقًا بالمستخدمين وFirebase: لوحة مرسومة، قطع متحركة، نرد، أدوار، ووضع فردي أو ٤ لاعبين.",
                style = MaterialTheme.typography.bodyMedium,
                color = Color(0xFF6B5A74),
            )
        }
    }
}

@Composable
private fun GameModeSelector(
    selectedMode: LudoGameMode,
    onModeSelected: (LudoGameMode) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        LudoGameMode.entries.forEach { mode ->
            FilterChip(
                selected = selectedMode == mode,
                onClick = { onModeSelected(mode) },
                label = { Text(mode.label) },
            )
        }
    }
}

@Composable
private fun TurnPanel(
    state: LudoUiState,
    onRollDice: () -> Unit,
    onReset: () -> Unit,
) {
    val turnColor by animateColorAsState(
        targetValue = state.currentTurn.toColor(),
        label = "turn-color",
    )

    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(containerColor = Color.White.copy(alpha = 0.94f)),
        shape = RoundedCornerShape(26.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(64.dp)
                    .shadow(10.dp, CircleShape)
                    .clip(CircleShape)
                    .background(turnColor),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = state.diceValue?.toString() ?: "-",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Black,
                    color = Color.White,
                )
            }

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = state.winner?.let { "الفائز: ${it.label}" }
                        ?: "الدور: ${state.currentTurn.label}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF2B2233),
                )
                Text(
                    text = if (state.currentPlayer.isBot) "الكمبيوتر يلعب الآن" else state.statusMessage,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF6B5A74),
                )
            }

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    enabled = state.canRoll && !state.currentPlayer.isBot && state.winner == null,
                    onClick = onRollDice,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF7851A9)),
                ) {
                    Text("ارم النرد")
                }
                OutlinedButton(onClick = onReset) {
                    Text("إعادة")
                }
            }
        }
    }
}

@Composable
private fun LudoBoardCard(
    state: LudoUiState,
    onPieceClick: (Int) -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White.copy(alpha = 0.92f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
        shape = RoundedCornerShape(32.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            contentAlignment = Alignment.Center,
        ) {
            LudoBoard(
                state = state,
                onPieceClick = onPieceClick,
            )
        }
    }
}

@Composable
private fun LudoBoard(
    state: LudoUiState,
    onPieceClick: (Int) -> Unit,
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(1f),
        contentAlignment = Alignment.Center,
    ) {
        val boardSize = if (maxWidth < maxHeight) maxWidth else maxHeight
        val cellSize = boardSize / BOARD_SIDE_CELLS
        val pieceSize = cellSize * 0.74f
        val pieceTargets = remember(state.pieces) {
            state.pieces.associate { piece -> piece.id to LudoBoardLayout.cellForPiece(piece) }
        }
        val occupied = pieceTargets.entries.groupBy { it.value.occupancyKey }

        Box(modifier = Modifier.size(boardSize)) {
            Canvas(modifier = Modifier.matchParentSize()) {
                drawBoardBackground()
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

                Box(
                    modifier = Modifier
                        .offset(x = animatedX, y = animatedY)
                        .size(pieceSize)
                        .zIndex(if (canMove) 2f else 1f)
                        .shadow(if (canMove) 10.dp else 5.dp, CircleShape)
                        .clip(CircleShape)
                        .background(piece.owner.toColor())
                        .border(
                            width = if (canMove) 3.dp else 1.dp,
                            color = if (canMove) Color.White else Color.Black.copy(alpha = 0.16f),
                            shape = CircleShape,
                        )
                        .clickable(enabled = canMove) { onPieceClick(piece.id) },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = ((piece.id % PIECES_PER_PLAYER) + 1).toString(),
                        color = Color.White,
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Black,
                    )
                }
            }
        }
    }
}

@Composable
private fun AvailableMoves(
    state: LudoUiState,
    onPieceClick: (Int) -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White.copy(alpha = 0.84f)),
        shape = RoundedCornerShape(24.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "الحركات المتاحة",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF2B2233),
            )
            if (state.availablePieceIds.isEmpty() || state.currentPlayer.isBot) {
                Text(
                    text = state.statusMessage,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF6B5A74),
                )
            } else {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(state.availablePieceIds.toList().sorted()) { pieceId ->
                        val piece = state.pieces.first { it.id == pieceId }
                        AssistChip(
                            onClick = { onPieceClick(pieceId) },
                            label = {
                                Text("${piece.owner.label} - قطعة ${(piece.id % PIECES_PER_PLAYER) + 1}")
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PlayerSummaryGrid(state: LudoUiState) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        state.players.chunked(2).forEach { rowPlayers ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                rowPlayers.forEach { player ->
                    PlayerSummaryCard(
                        player = player,
                        pieces = state.pieces.filter { it.owner == player.color },
                        isCurrentTurn = state.currentTurn == player.color,
                        modifier = Modifier.weight(1f),
                    )
                }
                if (rowPlayers.size == 1) {
                    Spacer(modifier = Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun PlayerSummaryCard(
    player: LudoPlayer,
    pieces: List<LudoPiece>,
    isCurrentTurn: Boolean,
    modifier: Modifier = Modifier,
) {
    val finished = pieces.count { it.isFinished }
    val inHome = pieces.count { it.isAtHome }

    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrentTurn) player.color.toColor().copy(alpha = 0.15f) else Color.White,
        ),
        shape = RoundedCornerShape(22.dp),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(16.dp)
                        .clip(CircleShape)
                        .background(player.color.toColor()),
                )
                Text(
                    text = player.color.label,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF2B2233),
                )
            }
            Text(
                text = if (player.isBot) "كمبيوتر" else "لاعب",
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF6B5A74),
            )
            Text(
                text = "وصلت: $finished / $PIECES_PER_PLAYER - في البيت: $inHome",
                style = MaterialTheme.typography.labelMedium,
                color = Color(0xFF51445D),
            )
        }
    }
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawBoardBackground() {
    val boardSize = size.minDimension
    val cell = boardSize / BOARD_SIDE_CELLS
    val stroke = 1.dp.toPx()

    drawRoundRect(
        color = Color(0xFFFDF7EC),
        size = Size(boardSize, boardSize),
        cornerRadius = CornerRadius(32.dp.toPx()),
    )

    LudoBoardLayout.homeBlocks.forEach { block ->
        drawRoundRect(
            color = block.color.toColor().copy(alpha = 0.18f),
            topLeft = Offset(block.col * cell + cell * 0.2f, block.row * cell + cell * 0.2f),
            size = Size(cell * 5.6f, cell * 5.6f),
            cornerRadius = CornerRadius(cell * 0.75f),
        )
    }

    LudoBoardLayout.trackCells.forEachIndexed { index, grid ->
        val safeColor = LudoBoardLayout.safeCellColor(index)?.toColor()?.copy(alpha = 0.28f)
        drawCell(
            col = grid.col,
            row = grid.row,
            cell = cell,
            fill = safeColor ?: Color.White,
            strokeWidth = stroke,
        )
    }

    LudoBoardLayout.homeLanes.forEach { (color, lane) ->
        lane.forEach { grid ->
            drawCell(
                col = grid.col,
                row = grid.row,
                cell = cell,
                fill = color.toColor().copy(alpha = 0.36f),
                strokeWidth = stroke,
            )
        }
    }

    LudoBoardLayout.homeYards.forEach { (color, cells) ->
        cells.forEach { grid ->
            drawCircle(
                color = color.toColor().copy(alpha = 0.26f),
                radius = cell * 0.34f,
                center = Offset((grid.col + 0.5f) * cell, (grid.row + 0.5f) * cell),
            )
        }
    }

    drawRoundRect(
        color = Color(0xFF33214F),
        topLeft = Offset(cell * 6.35f, cell * 6.35f),
        size = Size(cell * 2.3f, cell * 2.3f),
        cornerRadius = CornerRadius(cell * 0.46f),
    )
    drawCircle(
        color = Color.White.copy(alpha = 0.92f),
        radius = cell * 0.62f,
        center = Offset(cell * 7.5f, cell * 7.5f),
    )
    drawCircle(
        color = Color(0xFFFF9F1C),
        radius = cell * 0.35f,
        center = Offset(cell * 7.5f, cell * 7.5f),
    )
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawCell(
    col: Int,
    row: Int,
    cell: Float,
    fill: Color,
    strokeWidth: Float,
) {
    val inset = cell * 0.06f
    drawRoundRect(
        color = fill,
        topLeft = Offset(col * cell + inset, row * cell + inset),
        size = Size(cell - inset * 2, cell - inset * 2),
        cornerRadius = CornerRadius(cell * 0.18f),
    )
    drawRoundRect(
        color = Color.Black.copy(alpha = 0.11f),
        topLeft = Offset(col * cell + inset, row * cell + inset),
        size = Size(cell - inset * 2, cell - inset * 2),
        cornerRadius = CornerRadius(cell * 0.18f),
        style = Stroke(strokeWidth),
    )
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
        LudoPlayerColor.Red to listOf(GridCell(2, 11), GridCell(3, 11), GridCell(2, 12), GridCell(3, 12)),
        LudoPlayerColor.Green to listOf(GridCell(2, 2), GridCell(3, 2), GridCell(2, 3), GridCell(3, 3)),
        LudoPlayerColor.Yellow to listOf(GridCell(11, 2), GridCell(12, 2), GridCell(11, 3), GridCell(12, 3)),
        LudoPlayerColor.Blue to listOf(GridCell(11, 11), GridCell(12, 11), GridCell(11, 12), GridCell(12, 12)),
    )

    val homeBlocks = listOf(
        HomeBlock(LudoPlayerColor.Green, 0, 0),
        HomeBlock(LudoPlayerColor.Yellow, 9, 0),
        HomeBlock(LudoPlayerColor.Red, 0, 9),
        HomeBlock(LudoPlayerColor.Blue, 9, 9),
    )

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
