import aiofiles


class FileManager:
    async def load(self, file_path: str) -> str:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
            return await file.read()

    async def save(self, file_path: str, content: str) -> None:
        async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
            await file.write(content)