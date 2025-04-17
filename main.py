# test_brainflow.py
from brainflow.board_shim
import BoardShim, BrainFlowInputParams, BoardIds

BoardShim.enable_dev_board_logger()
params = BrainFlowInputParams()
board = BoardShim(BoardIds.SYNTHETIC_BOARD, params)
board.prepare_session()
board.start_stream()
print("Streaming from synthetic board!")
board.stop_stream()
board.release_session()
