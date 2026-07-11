from pprint import pprint

import fluxer
from fluxer import Cog
from fluxer.checks import has_permission
import logging
import base64
import requests
import hashlib
import os

logger = logging.getLogger(__name__)

class LinuxLikeTools(Cog):
    def __init__(self, bot: fluxer.Bot):
        super().__init__(bot)
    
    @Cog.command()
    async def base64(self, ctx: fluxer.models.message.Message):
        """
        Description: Encodes or decodes a string using Base64 and file type detection.
        
        Usage: /base64 -d <string>  # decode | /base64 <string>  # encode
        """
        # Check if -d is set as flag
        content = ctx.content
        content = content.removeprefix("/base64 ")
        split_message = content.split()
        logger.log(logging.INFO,f"{ctx.content}")
        if content.startswith("-d "):
            content = content.removeprefix("-d ")
            original_string = content
            decoded_bytes = base64.b64decode(original_string)
            decoded_string = decoded_bytes.decode('utf-8')
            
            await ctx.reply(decoded_string)
            return
        else:
            original_string = content
            bytes_data = original_string.encode('utf-8')
            base64_bytes = base64.b64encode(bytes_data)
            base64_string = base64_bytes.decode('utf-8')
            
            await ctx.reply(base64_string)
            return
    
    def find_filetype(self, filebytes: bytes):
        """
        Find the file type of a given byte string.
        Based on the magic numbers of common file types.
        """
        magic_dict = {
            b'\xFF\xD8\xFF': 'jpg',
            b'\x89PNG\r\n\x1A\n': 'png',
            b'GIF87a': 'gif',
            b'GIF89a': 'gif',
            b'%PDF-': 'pdf',
            b'PK\x03\x04': 'zip',
            b'Rar!\x1A\x07\x00': 'rar',
            b'\x7FELF': 'elf',
            b'\x42\x4D': 'bmp',
            b'\x49\x49\x2A\x00': 'tif',
            b'\x4D\x4D\x00\x2A': 'tif',
            b'\x00\x00\x01\x00': 'ico',
            b'\x00\x00\x02\x00': 'cur',
            b'\x25\x21\x50\x53': 'ps',
            b'\xD0\xCF\x11\xE0': 'doc',
            b'\x50\x4B\x03\x04': 'docx',
            b'\x50\x4B\x05\x06': 'docx',
            b'\x50\x4B\x07\x08': 'docx',
            b'\xFF\xFB': 'mp3',
            b'\x49\x44\x33': 'mp3',
            b'\x00\x00\x00\x18ftyp3g': '3gp',
            b'\x00\x00\x00\x18ftypmp42': 'mp4',
            b'\x00\x00\x00\x14ftypisom': 'mp4',
            b'\x00\x00\x00\x14ftypMSNV': 'mp4',
            b'\x00\x00\x00\x14ftypavc1': 'mp4',
            b'\x00\x00\x00\x14ftypmmp4': 'mp4',
            b'\x00\x00\x00\x14ftypqt': 'mov',
            bytes([0x00, 0x00, 0x00, 0x14, 0x66, 0x74, 0x79, 0x70, 0x6D, 0x70, 0x34, 0x32]): 'mp4',
            b'\x00\x00\x00\x14ftypM4V ': 'mp4',
            b'\x00\x00\x00\x14ftypM4A ': 'mp4',
            b'\x00\x00\x00\x14ftypM4P ': 'mp4',
            b'\x00\x00\x00\x14ftypM4B ': 'mp4',
            b'\x00\x00\x00\x14ftypM4S ': 'mp4',
            b'\x00\x00\x00\x14ftypM4V\x20': 'mp4',
            b'\x00\x00\x00\x14ftypM4A\x20': 'mp4',
            b'\x00\x00\x00\x14ftypM4P\x20': 'mp4',
            b'\x00\x00\x00\x14ftypM4B\x20': 'mp4',
            b'\x00\x00\x00\x14ftypM4S\x20': 'mp4',
        }
        
        for magic, filetype in magic_dict.items():
            if filebytes.startswith(magic):
                return filetype
        return None
    
    
    @Cog.command()
    async def base64_file(self, ctx: fluxer.models.message.Message):
        """
        Description: Encodes or decodes a file using Base64 and a similar syntax to Linux.
        
        Usage: /base64_file -d <string>  # decode | /base64 <file as attachment>  # encode
        """
        
        # Check if -d is set as flag
        content = ctx.content
        content = content.removeprefix("/base64_file ")
        split_message = content.split()
        logger.log(logging.DEBUG,f"{ctx.content}")
        if content.startswith("-d "):
            content = content.removeprefix("-d ")
            original_string = content
            decoded_bytes = base64.b64decode(original_string)
            # decoded_string = decoded_bytes.decode('utf-8')
            ext = self.find_filetype(decoded_bytes) or "bin"
            filename = f"decoded_file.{ext}"
            logger.log(logging.INFO, "Sending reply")
            await ctx.reply("Here is your decoded file.", file=fluxer.File(fp=decoded_bytes, filename=filename))
            return
        else:
            message_attachments = ctx.attachments
            for message_attachment in message_attachments:
                response = requests.get(message_attachment.url)
                content_bytes = response.content
                base64_bytes = base64.b64encode(content_bytes)
                base64_string = base64_bytes.decode('utf-8')
                
                await ctx.reply(f"{message_attachment.filename}: {base64_string}")
            return
    
    @Cog.command()
    async def file_profile(self, ctx: fluxer.models.message.Message):
        """
        Description: Tries to find as much information about a file as possible.
        
        Usage: /file_profile 
        
        Man: Provide a file as attachment to this command.\nOptions:\n-a\t\tuse everything\n--hash\t\tgenerates all possible hashes of this file
        """
        
        content = ctx.content
        content = content.removeprefix("/file_profile ")
        split_message = content.split()
        
        message_attachments = ctx.attachments
        if not message_attachments:
            await ctx.reply("Please provide at least one file.")
            return
        
        embed_messages = {}
        #logger.log(logging.DEBUG,f"{ctx.content}")
        hash_messages       = {}
        ext_messages        = {}
        header_messages     = {}
        
        everything_flag = "-a" in split_message or "--all" in split_message
        logger.info(f"everything_flag is set to {everything_flag}")
        
        for message_attachment in message_attachments:
            file_content = requests.get(message_attachment.url).content
            
            header_message  = f"# File: `{message_attachment.filename}`\n"
            header_message += f"content_type: {message_attachment.content_type}\n"
            header_message += f"description: {message_attachment.description}\n"
            header_message += f"ephemeral: {message_attachment.ephemeral}\n"
            header_message += f"height: {message_attachment.height}\n"
            header_message += f"width: {message_attachment.width}\n"
            header_message += f"size: {message_attachment.size}\n"
            header_message += f"id: {message_attachment.id}\n"
            
            header_messages[message_attachment.id] = header_message
            
            
            
            # Generate hash info for a file
            if "--hash" in split_message or everything_flag:
                hash_message  =  "## Hashes: \n"
                hash_message += f"### For: `{message_attachment.filename}`\n"
                hash_message += f"sha1: {hashlib.sha1(file_content).hexdigest()}\n"
                hash_message += f"sha256: {hashlib.sha256(file_content).hexdigest()}\n"
                hash_message += f"sha512: {hashlib.sha512(file_content).hexdigest()}\n"
                hash_message += f"md5: {hashlib.md5(file_content).hexdigest()}\n"
                hash_message += f"sha3_256: {hashlib.sha3_256(file_content).hexdigest()}\n"
                hash_message += f"sha3_512: {hashlib.sha3_512(file_content).hexdigest()}\n"
                hash_messages[message_attachment.id] = hash_message
            
            if "--ext" in split_message or everything_flag:
                ext_message  =  "## Extensions\n"
                ext_message += f"### For: `{message_attachment.filename}`\n"
                ext_message += f"predicted: {self.find_filetype(file_content) or ""}\n"
                ext_message += f"based on filename: {str(os.path.splitext(message_attachment.filename)[-1]).removeprefix('.') if os.path.splitext(message_attachment.filename)[-1].startswith('.') else ""}\n"

                
                ext_messages[message_attachment.id] = ext_message
        
        
        
        
        if hash_messages:
            for key in hash_messages.keys():
                if key not in embed_messages.keys():
                    embed_messages[key] = {"header_message": header_messages[key]}
                embed_messages[key]["hash_message"] = hash_messages[key]

        if ext_messages:
            for key in ext_messages.keys():
                if key not in embed_messages.keys():
                    embed_messages[key] = {"id":key}
                embed_messages[key]["ext_message"] = ext_messages[key]
        
        
        print("DEBUG:cogs.linux_like_tools:PPRINT:")
        pprint(embed_messages)
        
        embeds = []
        
        for key in embed_messages.keys():
            message_parts_sorted = embed_messages[key].keys()
            if "id" in message_parts_sorted:
                message_parts_sorted.remove("id")
            embed_message = ""
            for part in message_parts_sorted:
                embed_message += embed_messages[key][part] + "\n"
            
            embed = fluxer.Embed(
                title=key,
                description=embed_message
            )
            embeds.append(embed)
        
        await ctx.reply(embeds=embeds)
        

        

async def setup(bot: fluxer.Bot):
    await bot.add_cog(LinuxLikeTools(bot))

async def teardown(bot):
    await bot.remove_cog("LinuxLikeTools")