import os
import asyncio
from os import environ as env
from typing import Tuple, List

from gtts import gTTS
from rich import print
import moviepy.editor as mp
from deepgram import Deepgram
from dotenv import load_dotenv
from googletrans import Translator, LANGUAGES

load_dotenv()


class DeepDubber:
    def __init__(self, *, video_path: os.PathLike) -> None:
        try:
            self.video = mp.VideoFileClip(video_path, audio=True)
            self.video_path = video_path
        except OSError:
            print("[bold red]Video not found.[/bold red] Exiting...")
            exit()

        print(f"[bold blue]Using Video path: [/bold blue] {self.video_path}")

    def __translate_subtitles(
        self, subtitles: List[Tuple[str, Tuple[float, float]]], *, language: str
    ) -> List[Tuple[str, Tuple[float, float]]]:
        """Translates the subtitles into the target language."""
        if not language in LANGUAGES.keys():
            print(f"[bold red]Language {language} not found.[/bold red] Exiting...")
            exit()
        print(f"⚡ Translating the subtitles into [red]{LANGUAGES[language]}[/red]")

        translator = Translator()
        words_list = [word for word, (start, end) in subtitles]

        translated_words = []

        for word in words_list:
            translation = translator.translate(word, dest=language)
            translated_words.append(translation.text)

        translated_subtitles = self.__create_translated_subtitles(
            translated_words, subtitles
        )

        # Removes previous line from terminal
        print("\033[F\033[K", end="")

        print(
            f"✅ [green]Translated the subtitles into [red]{LANGUAGES[language]}[/red]"
        )

        return translated_subtitles

    def __create_translated_subtitles(
        self,
        translated_words: List[str],
        subtitles: List[Tuple[str, Tuple[float, float]]],
    ) -> List[Tuple[str, Tuple[float, float]]]:
        """Creates the translated subtitles."""
        translated_subtitles = []

        for word, (start, end) in subtitles:
            translated_subtitles.append((translated_words.pop(0), (start, end)))
        return translated_subtitles

    def __convert_to_speech(
        self,
        subtitles: List[Tuple[str, Tuple[float, float]]],
        initial_lang: str = "en",
        output_file="output.mp4",
    ) -> None:
        """Converts the subtitles into speech and saves them to the disk."""
        print("⚡ Converting the subtitles into speech")

        audio_arr = []

        for word, (start, end) in subtitles:
            tts = gTTS(word, lang=initial_lang)
            audio_arr.append(tts)

        print("\033[F\033[K", end="")
        print("✅ [green]Converted the subtitles into speech.[/green]")

        os.makedirs("temp", exist_ok=True)
        # temperory folder to save the audio
        audio_folder = os.path.join(os.getcwd(), "temp")

        for i, audio in enumerate(audio_arr):
            audio.save(os.path.join(audio_folder, f"{i}.mp3"))

        print("⚡ Merging the audio files")
        audio_file = os.path.join(os.getcwd(), output_file)

        # Remove sound from original video
        final_vid = self.video.copy()
        final_vid.audio = None

        mp_audio_arr = []
        for i, audio in enumerate(os.listdir(audio_folder)):
            audio_clip = mp.AudioFileClip(os.path.join(audio_folder, f"{i}.mp3"))

            mp_audio_arr.append(
                audio_clip.set_fps(
                    final_vid.fps * (subtitles[i][1][0] - subtitles[i][1][1])
                ).set_start(subtitles[i][1][0])
            )

        final_vid.audio = mp.CompositeAudioClip(mp_audio_arr)
        print("\033[F\033[K", end="")
        print("✅ [green]Merged the audio files.[/green]")

        print("⚡ Saving the audio file")
        final_vid.write_videofile(audio_file, audio_codec="aac")
        print(f"✅ [green]Saved the final file.[/green]\n> [blue]{output_file}[/blue]")

    async def _get_subtitles(self) -> List[Tuple[float, str]]:
        """Runs the video path through Deepgram and returns the subtitles as a list of tuples."""
        # Initialises Deepgram
        dg_client = Deepgram(env.get("DEEPGRAM_KEY"))

        with open(self.video_path, "rb") as f:
            video_data = f.read()

        source = {"buffer": video_data, "mimetype": "video/mp4"}
        options = {"punctuate": True, "language": "en-US"}

        print("⚡ Fetching the Video Transcripts from [red]Deepgram[/red]")
        response = await dg_client.transcription.prerecorded(source, options)
        print("\033[F\033[K", end="")
        print(
            "✅ [green]Deepgram has sent back the subtitles.[/green] [blue]I will now process them and render them on the video.[/blue]"
        )

        subtitles = []

        # Iterates through the response and creates a list of tuples
        for word in response["results"]["channels"][0]["alternatives"][0]["words"]:
            word, start, end = word["word"], word["start"], word["end"]
            subtitles.append((word, (start, end)))

        return subtitles

    @staticmethod
    def cleanup() -> None:
        """Gets rid of all unnecessary files"""
        print("⚡ Cleaning up the files")
        try:
            # Delete temp folder
            for file in os.listdir("temp"):
                os.remove(os.path.join("temp", file))
            os.rmdir("temp")

            print("✅ [green]Deleted the temp folder.[/green]")
        except FileNotFoundError:
            print("✅ [red]No files to clean up.[/red]")

    def run(
        self,
        output_file="output.mp4",
        *,
        language: str,
        initial_lang: str = "en",
        cleanup: bool = True,
    ) -> None:
        """Gets the subtitles, Converts them into speech and dubs the video.

        Args:
            output_file (str, optional): The name of the output file. Defaults to "output.mp4".
            language (str): The language to translate the subtitles into.
            initial_lang (str, optional): The language of the subtitles. Defaults to "en".
            cleanup (bool, optional): Whether to delete the temp folder. Defaults to True.

        Language Codes:
            https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes

        Example:
            >>> dubber = DeepDubber("video.mp4")
            >>> dubber.run("output.mp4", language="es")
        """
        subtitles = asyncio.get_event_loop().run_until_complete(self._get_subtitles())
        subtitles = self.__translate_subtitles(subtitles, language=language)
        self.__convert_to_speech(
            subtitles, initial_lang=initial_lang, output_file=output_file
        )

        DeepDubber.cleanup() if cleanup else None

        print("⚡ Thanks for using DeepDubber! Have a nice day!")


if __name__ == "__main__":
    dubber = DeepDubber(video_path="./demo.mp4")
    dubber.run(language="fr", cleanup=False)
