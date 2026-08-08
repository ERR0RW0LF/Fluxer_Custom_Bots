import fluxer
from fluxer import Cog
import logging

logger = logging.getLogger(__name__)

SIZE_OF_BOARD = 3
WIN_PATTERNS = [
    [1, 1, 1, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 1, 1, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 1, 1],
    [1, 0, 0, 1, 0, 0, 1, 0, 0],
    [0, 1, 0, 0, 1, 0, 0, 1, 0],
    [0, 0, 1, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 1],
    [0, 0, 1, 0, 1, 0, 1, 0, 0]
]

num_to_reaction = {
    0: ":one:",
    1: ":two:",
    2: ":three:",
    3: ":four:",
    4: ":five:",
    5: ":six:",
    6: ":seven:",
    7: ":eight:",
    8: ":nine:"
}

reaction_to_num = {
    ":one:": 0,
    ":two:": 1,
    ":three:": 2,
    ":four:": 3,
    ":five:": 4,
    ":six:": 5,
    ":seven:": 6,
    ":eight:": 7,
    ":nine:": 8
}

class Tic_tac_toe(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
    
    @Cog.command()
    async def tic_tac_toe(self, ctx: fluxer.models.message.Message):
        """
        Description: Play a game of Tic Tac Toe with a friend or the bot.

        Usage: /tic_tac_toe @friend

        Man: Play a game of Tic Tac Toe with a friend or the bot.
        """

        game_board = list(range(0,SIZE_OF_BOARD**2))
        
        game_embed = fluxer.Embed(
            title="Tic Tac Toe",
            description=f"```\n{self.pretty_board(game_board)}\n```"
        )
        
        game_message = await ctx.reply(embed=game_embed)
        
        game_finished = False
        
        while not(game_finished):
            for num in game_board:
                await game_message.add_reaction(num_to_reaction[num])
            break
    
    
    def pattern_check(self, board: list) -> tuple[bool, str]:
        has_winner = False
        winner = None
        possible_winner = None
        
        for pattern in WIN_PATTERNS:
            for cell_n in range(0,len(pattern)):
                pattern_cell = pattern[cell_n]
                cell = board[cell_n]
                if not(possible_winner) and pattern_cell == 1:
                    if str(cell).isdigit():
                        break
                    possible_winner = str(cell)
                elif pattern_cell == 1:
                    if str(cell) != possible_winner:
                        winner = None
                        break
                    winner = cell
            if winner: 
                break
        
        
        
        return (has_winner, winner)
    
    def pretty_board(self, board: list) -> str:
        board_string = ""
        for cell_absolute_n in range(0,SIZE_OF_BOARD**2):
            cell_n = cell_absolute_n % SIZE_OF_BOARD
            if cell_n == 0:
                board_string = board_string + " "
            board_string = board_string + f"{board[cell_absolute_n]}"
            if cell_n == 2:
                board_string = board_string + "\n"
                if (cell_absolute_n % (SIZE_OF_BOARD**2-1)) != 0:
                    board_string = board_string + ("-"*11) + "\n"
                else:
                    board_string = board_string[:-1]
            else:
                board_string = board_string + " | "
        
        return board_string
    

async def setup(bot: fluxer.Bot):
    await bot.add_cog(Tic_tac_toe(bot))

async def teardown(bot):
    await bot.remove_cog("tic_tac_toe")
