import fluxer
from fluxer import Cog
import logging

logger = logging.getLogger(__name__)

SIZE_OF_BOARD = 3

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
    
    def pretty_board(self, board: list) -> str:
        board_string = ""
        for cell_absolute_n in range(0,SIZE_OF_BOARD**2):
            cell_n = cell_absolute_n % SIZE_OF_BOARD
            if cell_n == 0:
                board_string = board_string + " "
            board_string = board_string + f"{board[cell_absolute_n]}"
            if cell_n == 2:
                board_string = board_string + "\n"
                print(cell_absolute_n % (SIZE_OF_BOARD**2-1))
                if (cell_absolute_n % (SIZE_OF_BOARD**2-1)) != 0:
                    board_string = board_string + ("-"*11) + "\n"
            else:
                board_string = board_string + " | "
        
        return board_string
    

async def setup(bot: fluxer.Bot):
    await bot.add_cog(Tic_tac_toe(bot))

async def teardown(bot):
    await bot.remove_cog("tic_tac_toe")
