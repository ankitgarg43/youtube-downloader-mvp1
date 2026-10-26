import json
import io
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import webbrowser

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import yt_dlp
from yt_dlp.postprocessor.metadataparser import MetadataParserPP

# --- Constants ---
APP_NAME = "YT Downloader"
APP_VERSION = "1.0.0"
APP_DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / APP_NAME
HISTORY_FILE = APP_DATA_DIR / "download_history.json"
MAX_RETRIES = 3
COLORS = {
    "background": "#101318",
    "panel": "#191E25",
    "panel_alt": "#202630",
    "border": "#2B333E",
    "text": "#F3F5F7",
    "muted": "#929DAA",
    "accent": "#4C8DFF",
    "accent_hover": "#3479F4",
    "success": "#52C28B",
}


class YouTubeDownloaderApp(ctk.CTk):
    def __init__(self):
        """Initialize the main application window and UI."""
        super().__init__()

        self.title("YT Download")
        self.geometry("410x292")
        self.minsize(370, 270)
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=COLORS["background"])

        self.download_directory = ctk.StringVar(value=str(Path.home() / "Downloads"))
        self.download_format = ctk.StringVar(value="mp4")
        self.download_history = self.load_history()
        self.is_downloading = False
        self._preview_request_id = 0
        self._preview_after_id = None
        self.preview_image = None

        self.create_widgets()

    def create_widgets(self):
        """Build a minimal dark widget for quick downloads."""
        self.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(10, 7), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text="▶",
            text_color=COLORS["accent"],
            font=ctk.CTkFont(size=18, weight="bold"),
            width=24,
        ).grid(row=0, column=0, padx=(0, 5), sticky="w")
        ctk.CTkLabel(
            header,
            text="YT / DOWNLOAD",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, sticky="w")
        self.header_history_button = ctk.CTkButton(
            header,
            text="◷",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=COLORS["panel_alt"],
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=17),
            command=self.show_history,
        )
        self.header_history_button.grid(row=0, column=2, padx=(4, 0), sticky="e")
        self.header_settings_button = ctk.CTkButton(
            header,
            text="⚙",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=COLORS["panel_alt"],
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=15),
            command=self.show_settings,
        )
        self.header_settings_button.grid(row=0, column=3, padx=(2, 0), sticky="e")

        card = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color=COLORS["panel"],
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=1, column=0, padx=12, pady=2, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        url_frame = ctk.CTkFrame(card, fg_color="transparent")
        url_frame.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(
            url_frame,
            height=34,
            corner_radius=8,
            border_color=COLORS["border"],
            fg_color=COLORS["panel_alt"],
            text_color=COLORS["text"],
            placeholder_text="Paste YouTube link...",
            placeholder_text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12),
        )
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.bind("<KeyRelease>", self.on_url_changed)
        self.url_entry.bind("<Return>", lambda event: self.start_download_thread())
        self.paste_button = ctk.CTkButton(
            url_frame,
            text="▣",
            width=34,
            height=34,
            corner_radius=8,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.paste_url,
        )
        self.paste_button.grid(row=0, column=1, padx=(6, 0))

        self.preview_card = ctk.CTkFrame(
            card,
            corner_radius=9,
            fg_color=COLORS["panel_alt"],
            border_width=1,
            border_color=COLORS["border"],
        )
        self.preview_card.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        self.preview_card.grid_columnconfigure(1, weight=1)
        self.preview_card.grid_remove()
        self.preview_thumbnail = ctk.CTkLabel(
            self.preview_card,
            text="▶",
            width=112,
            height=64,
            corner_radius=6,
            fg_color=COLORS["panel"],
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=22),
        )
        self.preview_thumbnail.grid(row=0, column=0, rowspan=3, padx=(8, 10), pady=8)
        self.preview_title = ctk.CTkLabel(
            self.preview_card,
            text="Fetching video…",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=220,
        )
        self.preview_title.grid(row=0, column=1, padx=(0, 8), pady=(9, 2), sticky="ew")
        self.preview_channel = ctk.CTkLabel(
            self.preview_card,
            text="",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=10),
            anchor="w",
        )
        self.preview_channel.grid(row=1, column=1, padx=(0, 8), sticky="ew")
        self.preview_duration = ctk.CTkLabel(
            self.preview_card,
            text="",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=10),
            anchor="w",
        )
        self.preview_duration.grid(row=2, column=1, padx=(0, 8), pady=(1, 8), sticky="ew")

        options = ctk.CTkFrame(card, fg_color="transparent")
        options.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="ew")
        options.grid_columnconfigure(0, weight=1)
        self.format_menu = ctk.CTkSegmentedButton(
            options,
            values=["MP4", "MP3", "BEST"],
            height=30,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["panel_alt"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.set_format,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.format_menu.set("MP4")
        self.format_menu.grid(row=0, column=0, sticky="ew")

        dir_frame = ctk.CTkFrame(card, fg_color="transparent")
        dir_frame.grid(row=3, column=0, padx=10, pady=(0, 8), sticky="ew")
        dir_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            dir_frame,
            text="↓",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=15, weight="bold"),
            width=20,
        ).grid(row=0, column=0, padx=(0, 4))
        self.dir_label = ctk.CTkLabel(
            dir_frame,
            text=self._compact_path(self.download_directory.get()),
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.dir_label.grid(row=0, column=1, sticky="ew")
        self.browse_button = ctk.CTkButton(
            dir_frame,
            text="…",
            width=32,
            height=26,
            fg_color="transparent",
            hover_color=COLORS["border"],
            text_color=COLORS["muted"],
            command=self.browse_directory,
        )
        self.browse_button.grid(row=0, column=2, padx=(4, 0))

        self.download_button = ctk.CTkButton(
            card,
            text="↓  DOWNLOAD",
            height=38,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.start_download_thread,
        )
        self.download_button.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="ew")

        progress_card = ctk.CTkFrame(self, fg_color="transparent")
        progress_card.grid(row=2, column=0, padx=16, pady=(7, 4), sticky="ew")
        progress_card.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(
            progress_card,
            text="READY",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="ew")
        self.progress_value_label = ctk.CTkLabel(
            progress_card,
            text="",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=10),
        )
        self.progress_value_label.grid(row=0, column=1, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(
            progress_card,
            height=4,
            corner_radius=2,
            progress_color=COLORS["accent"],
            fg_color=COLORS["panel_alt"],
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, columnspan=2, pady=(4, 0), sticky="ew")

    def browse_directory(self):
        """Open a folder chooser dialog and update the target directory."""
        initial_dir = self.download_directory.get() or str(Path.home() / "Downloads")
        selected_dir = filedialog.askdirectory(initialdir=initial_dir)
        if selected_dir:
            self.download_directory.set(selected_dir)
            self.dir_label.configure(text=self._compact_path(selected_dir))
            self.update_status(f"Directory set to: {selected_dir}")

    @staticmethod
    def _compact_path(path):
        """Keep the chosen folder readable in the narrow widget."""
        value = str(path)
        return value if len(value) <= 38 else f"...{value[-35:]}"

    def set_format(self, selected_format):
        """Map the friendly format selector to yt-dlp's output modes."""
        self.download_format.set({"MP4": "mp4", "MP3": "mp3", "BEST": "best"}.get(selected_format, "mp4"))

    def paste_url(self):
        """Paste clipboard text into the URL field."""
        try:
            value = self.clipboard_get().strip()
        except tk.TclError:
            self.show_warning("Clipboard empty", "Copy a YouTube link first, then try again.")
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, value)
        self.url_entry.focus_set()
        self.on_url_changed()

    def open_download_folder(self):
        """Open the selected output folder in Windows Explorer."""
        folder = Path(self.download_directory.get())
        if not folder.is_dir():
            self.show_warning("Folder not found", "Choose or create a download folder first.")
            return
        os.startfile(str(folder))

    def show_settings(self):
        """Show secondary actions in a dark, compact settings panel."""
        settings = ctk.CTkToplevel(self)
        settings.title("Settings")
        settings.geometry("250x300")
        settings.resizable(False, False)
        settings.configure(fg_color=COLORS["background"])
        settings.transient(self)
        settings.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            settings,
            text="SETTINGS",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        actions = [
            ("Open download folder", self.open_download_folder),
            ("Quick help", self.show_help),
            ("Check for updates", self.check_for_updates),
            ("Update yt-dlp", self.update_ytdlp),
            ("About", self.show_about),
            ("Third-party licenses", self.show_third_party_notices),
        ]
        for row, (label, command) in enumerate(actions, start=1):
            ctk.CTkButton(
                settings,
                text=label,
                height=34,
                fg_color=COLORS["panel"],
                hover_color=COLORS["panel_alt"],
                text_color=COLORS["text"],
                anchor="w",
                command=command,
            ).grid(row=row, column=0, padx=10, pady=3, sticky="ew")

    def on_url_changed(self, _event=None):
        """Debounce pasted/typed links before starting a background preview lookup."""
        if self._preview_after_id is not None:
            self.after_cancel(self._preview_after_id)
            self._preview_after_id = None
        self._preview_request_id += 1
        url = self.url_entry.get().strip()
        if not url:
            self.preview_card.grid_remove()
            self.geometry("410x292")
            return
        self._preview_after_id = self.after(650, lambda current_url=url: self.request_preview(current_url))

    def request_preview(self, url):
        """Show a preview card and fetch video metadata outside the UI thread."""
        self._preview_after_id = None
        host = urlparse(url).hostname or ""
        if host.lower().removeprefix("www.") not in {"youtube.com", "m.youtube.com", "youtu.be"}:
            self.show_preview_error("Not a YouTube link")
            return

        self._preview_request_id += 1
        request_id = self._preview_request_id
        self.preview_title.configure(text="Fetching video…")
        self.preview_channel.configure(text="")
        self.preview_duration.configure(text="")
        self.preview_thumbnail.configure(image=None, text="▶")
        self.preview_image = None
        self.preview_card.grid()
        self.geometry("410x382")
        threading.Thread(
            target=self._preview_worker,
            args=(url, request_id),
            daemon=True,
        ).start()

    def _preview_worker(self, url, request_id):
        """Resolve one video and its thumbnail without blocking the window."""
        try:
            bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            deno_path = bundle_root / "deno.exe"
            deno_location = str(deno_path) if deno_path.is_file() else shutil.which("deno")
            options = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 15,
            }
            if deno_location:
                options["js_runtimes"] = {"deno": {"path": deno_location}}
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
            if not isinstance(info, dict):
                raise ValueError("Video information was unavailable.")

            thumbnail_url = info.get("thumbnail")
            if not thumbnail_url and info.get("thumbnails"):
                thumbnail_url = next(
                    (item.get("url") for item in reversed(info["thumbnails"]) if item.get("url")),
                    None,
                )
            thumbnail = None
            if thumbnail_url:
                request = Request(thumbnail_url, headers={"User-Agent": APP_NAME})
                with urlopen(request, timeout=12) as response:
                    image_data = response.read(5 * 1024 * 1024 + 1)
                if len(image_data) > 5 * 1024 * 1024:
                    raise ValueError("The video thumbnail is unexpectedly large.")
                with Image.open(io.BytesIO(image_data)) as image:
                    thumbnail = image.convert("RGB")

            self.after(
                0,
                lambda details=info, image=thumbnail, token=request_id:
                    self.show_preview(details, image, token),
            )
        except Exception as exc:
            self.after(0, lambda error=str(exc), token=request_id: self.show_preview_error(error, token))

    def show_preview(self, info, thumbnail, request_id):
        """Render the fetched title, channel, duration and optional thumbnail."""
        if request_id != self._preview_request_id:
            return
        title = info.get("title") or "Untitled video"
        channel = info.get("channel") or info.get("uploader") or "Unknown channel"
        duration = info.get("duration")
        if isinstance(duration, (int, float)):
            total_seconds = int(duration)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_text = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
        else:
            duration_text = "Duration unavailable"
        self.preview_title.configure(text=title)
        self.preview_channel.configure(text=channel)
        self.preview_duration.configure(text=duration_text)
        if thumbnail is not None:
            self.preview_image = ctk.CTkImage(
                light_image=thumbnail,
                dark_image=thumbnail,
                size=(112, 64),
            )
            self.preview_thumbnail.configure(image=self.preview_image, text="")
        else:
            self.preview_thumbnail.configure(image=None, text="▶")

    def show_preview_error(self, message, request_id=None):
        """Display lookup or validation errors directly in the preview card."""
        if request_id is not None and request_id != self._preview_request_id:
            return
        self.preview_card.grid()
        self.geometry("410x382")
        self.preview_thumbnail.configure(image=None, text="!")
        self.preview_title.configure(text="Preview unavailable")
        self.preview_channel.configure(text=message[:55])
        self.preview_duration.configure(text="")

    def show_help(self):
        """Show concise usage and format guidance."""
        messagebox.showinfo(
            "Quick help",
            "1. Paste a YouTube video or playlist link.\n"
            "2. Choose MP4 video, MP3 audio, or Best.\n"
            "3. Select a save folder if needed, then choose Download.\n\n"
            "MP3 conversion and artwork embedding require FFmpeg. "
            "Some metadata fields depend on what the source provides.",
            parent=self,
        )

    def show_about(self):
        """Show application and yt-dlp version information."""
        messagebox.showinfo(
            "About YT Downloader",
            f"{APP_NAME} {APP_VERSION}\nyt-dlp {yt_dlp.version.__version__}",
            parent=self,
        )

    def show_third_party_notices(self):
        """Open the bundled third-party license and source notices."""
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        notice_path = bundle_root / "THIRD_PARTY_NOTICES.txt"
        if not notice_path.is_file():
            self.show_warning("Notices unavailable", f"Could not find:\n{notice_path}")
            return
        os.startfile(str(notice_path))

    def check_for_updates(self):
        """Check the latest yt-dlp release without blocking the interface."""
        self.update_status("Checking for yt-dlp updates...")
        threading.Thread(target=self._check_for_updates_worker, daemon=True).start()

    def _check_for_updates_worker(self):
        request = Request(
            "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": APP_NAME},
        )
        try:
            with urlopen(request, timeout=10) as response:
                release = json.loads(response.read().decode("utf-8"))
            latest = release.get("tag_name", "unknown")
            current = yt_dlp.version.__version__
            if latest.lstrip("v") == current.lstrip("v"):
                message = f"yt-dlp {current} is up to date."
            else:
                message = (
                    f"Latest yt-dlp release: {latest}\n"
                    f"Installed version: {current}\n\n"
                    "Choose Help → Updates → Update yt-dlp to update the source install, "
                    "or open the official release page for packaged builds."
                )
            self.after(0, lambda: messagebox.showinfo("Update check", message, parent=self))
            self.update_status("Update check complete")
        except (OSError, ValueError, KeyError) as exc:
            self.after(
                0,
                lambda error=exc: messagebox.showerror(
                    "Update check failed",
                    f"Could not check for updates:\n{error}",
                    parent=self,
                ),
            )
            self.update_status("Could not check for updates")

    def update_ytdlp(self):
        """Update yt-dlp in a source install or open the official release page."""
        if getattr(sys, "frozen", False):
            webbrowser.open("https://github.com/yt-dlp/yt-dlp/releases/latest")
            messagebox.showinfo(
                "Packaged app",
                "This standalone build includes its own yt-dlp version. "
                "Install a newer packaged app build to update the bundled downloader.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Update yt-dlp",
            "Upgrade yt-dlp in the Python environment used to run this app?",
            parent=self,
        ):
            return
        self.update_status("Updating yt-dlp...")
        threading.Thread(target=self._update_ytdlp_worker, daemon=True).start()

    def _update_ytdlp_worker(self):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.after(0, lambda: messagebox.showinfo(
                "Update complete",
                "yt-dlp was updated. Restart the app to use the new version.",
                parent=self,
            ))
            self.update_status("yt-dlp updated; restart the app")
        except (OSError, subprocess.SubprocessError) as exc:
            self.after(0, lambda error=exc: messagebox.showerror(
                "Update failed", f"Could not update yt-dlp:\n{error}", parent=self
            ))
            self.update_status("yt-dlp update failed")

    def update_status(self, message):
        """Safely update the status label from any thread."""
        if len(message) > 42:
            message = f"{message[:39]}..."
        try:
            self.after(0, lambda text=message: self.status_label.configure(text=text))
        except RuntimeError:
            return

    def show_error(self, title, message):
        """Safely show a message box from any thread."""
        try:
            self.after(0, lambda: messagebox.showerror(title, message))
        except RuntimeError:
            return

    def show_warning(self, title, message):
        """Safely show a warning box from any thread."""
        try:
            self.after(0, lambda: messagebox.showwarning(title, message))
        except RuntimeError:
            return

    def start_download_thread(self):
        """Start the download in a worker thread so the UI stays responsive."""
        if self.is_downloading:
            self.show_warning("In Progress", "A download is already in progress.")
            return

        url = self.url_entry.get().strip()
        if not url:
            self.show_error("Error", "Please enter a YouTube URL.")
            return

        host = urlparse(url).hostname or ""
        if host.lower().removeprefix("www.") not in {"youtube.com", "m.youtube.com", "youtu.be"}:
            self.show_error("Invalid URL", "Please provide a valid YouTube URL.")
            return

        self.is_downloading = True
        self.download_button.configure(state="disabled", text="Downloading...")
        self.progress_bar.set(0)
        self.progress_value_label.configure(text="")
        self.update_status("Starting download...")

        download_thread = threading.Thread(target=self.download_video, args=(url,), daemon=True)
        download_thread.start()

    def download_video(self, url):
        """Download a video or playlist with retry logic and history tracking."""
        output_dir = self.download_directory.get()
        try:
            os.makedirs(output_dir, exist_ok=True)
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    ydl_opts = self.build_yt_dlp_options(output_dir)
                    ydl_opts["progress_hooks"] = [self.progress_hook]
                    ydl_opts["ignoreerrors"] = True
                    ydl_opts["noplaylist"] = "playlist" not in url.lower()

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info_dict = ydl.extract_info(url, download=True)

                    if info_dict is None:
                        raise ValueError("No metadata was returned for the requested URL.")

                    self.add_to_history(info_dict)
                    self.save_history()
                    self.update_status("Download complete!")
                    break
                except Exception as exc:
                    if attempt >= MAX_RETRIES:
                        self.show_error("Download Failed", f"Failed to download after {MAX_RETRIES} attempts.\nError: {exc}")
                        self.update_status(f"Error after {MAX_RETRIES} attempts")
                        break

                    self.update_status(f"Attempt {attempt}/{MAX_RETRIES} failed. Retrying...")
                    time.sleep(1)
        except OSError as exc:
            self.show_error("Download folder error", f"Could not prepare the download folder:\n{exc}")
            self.update_status("Could not prepare download folder")
        finally:
            self.after(100, self.reset_ui_after_download)

    def build_yt_dlp_options(self, output_dir):
        """Create the yt-dlp configuration based on the selected format."""
        download_format = self.download_format.get().lower()
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        ffmpeg_path = bundle_root / "ffmpeg.exe"
        ffmpeg_location = str(ffmpeg_path) if ffmpeg_path.is_file() else None
        deno_path = bundle_root / "deno.exe"
        if not deno_path.is_file():
            deno_location = shutil.which("deno")
        else:
            deno_location = str(deno_path)
        metadata_postprocessors = [
            {
                "key": "MetadataParser",
                "when": "pre_process",
                "actions": [
                    (MetadataParserPP.Actions.INTERPRET, "%(id)s", "meta_id"),
                    (MetadataParserPP.Actions.INTERPRET, "%(title)s", "meta_title"),
                    (MetadataParserPP.Actions.REPLACE, "title", r"[. ]+$", ""),
                ],
            },
            {"key": "FFmpegMetadata", "add_metadata": True},
        ]
        filename_options = {
            "windowsfilenames": True,
            "restrictfilenames": True,
        }

        if download_format == "mp3":
            return {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                **filename_options,
                "writethumbnail": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "0",
                    },
                    *metadata_postprocessors,
                    {"key": "EmbedThumbnail"},
                ],
                "quiet": True,
                "no_warnings": True,
                "ffmpeg_location": ffmpeg_location,
                "js_runtimes": {"deno": {"path": deno_location}} if deno_location else {},
            }

        if download_format == "mp4":
            return {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": outtmpl,
                "quiet": True,
                "no_warnings": True,
                "merge_output_format": "mp4",
                **filename_options,
                "postprocessors": metadata_postprocessors,
                "ffmpeg_location": ffmpeg_location,
                "js_runtimes": {"deno": {"path": deno_location}} if deno_location else {},
            }

        return {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            **filename_options,
            "postprocessors": metadata_postprocessors,
            "ffmpeg_location": ffmpeg_location,
            "js_runtimes": {"deno": {"path": deno_location}} if deno_location else {},
        }

    def reset_ui_after_download(self):
        """Reset UI controls after a finished or failed download."""
        self.is_downloading = False
        self.download_button.configure(state="normal", text="Download")
        if self.status_label.cget("text").endswith("complete!"):
            self.progress_bar.set(1)

    def progress_hook(self, d):
        """Update the UI as yt-dlp downloads media."""
        status = d.get("status")
        if status == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded_bytes = d.get("downloaded_bytes", 0)
            filename = d.get("filename", "video")
            display_name = os.path.basename(filename)
            if len(display_name) > 50:
                display_name = display_name[:47] + "..."

            if total_bytes > 0:
                progress = min(downloaded_bytes / total_bytes, 1.0)
                percent = round(progress * 100)
                self.after(0, lambda p=progress: self.progress_bar.set(p))
                self.after(0, lambda value=percent: self.progress_value_label.configure(text=f"{value}%"))
                self.update_status(f"Downloading {display_name}")
        elif status == "finished":
            self.after(0, lambda: self.progress_bar.set(1))
            self.after(0, lambda: self.progress_value_label.configure(text="Processing"))
            self.update_status("Finished downloading. Processing...")

    def load_history(self):
        """Load the download history from disk."""
        try:
            APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
            if HISTORY_FILE.exists():
                with HISTORY_FILE.open("r", encoding="utf-8") as file:
                    history = json.load(file)
                    return history if isinstance(history, list) else []
        except (OSError, json.JSONDecodeError):
            return []
        return []

    def save_history(self):
        """Persist the current download history to disk."""
        try:
            APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
            with HISTORY_FILE.open("w", encoding="utf-8") as file:
                json.dump(self.download_history, file, indent=4)
        except OSError as exc:
            self.show_error("History Error", f"Could not save history file: {exc}")

    def add_to_history(self, info_dict):
        """Add a single video or entire playlist to the history list."""
        if isinstance(info_dict, dict) and info_dict.get("entries"):
            entries = info_dict.get("entries") or []
            for entry in entries:
                if entry is not None:
                    self._add_single_entry_to_history(entry)
            return

        self._add_single_entry_to_history(info_dict)

    def _add_single_entry_to_history(self, entry):
        """Add one record to the history."""
        record = {
            "title": entry.get("title", "N/A"),
            "url": entry.get("webpage_url") or entry.get("url") or "N/A",
            "download_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "directory": self.download_directory.get(),
        }
        self.download_history.insert(0, record)

    def show_history(self):
        """Create a new window and display the download history."""
        history_window = ctk.CTkToplevel(self)
        history_window.title("Download History")
        history_window.geometry("700x500")

        history_text = tk.Text(
            history_window,
            wrap="word",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 11),
            relief="flat",
            padx=12,
            pady=12,
        )
        history_text.pack(expand=True, fill="both", padx=10, pady=10)

        if not self.download_history:
            history_text.insert("1.0", "No download history found.")
        else:
            for item in self.download_history:
                entry = (
                    f"Title: {item.get('title', 'N/A')}\n"
                    f"URL: {item.get('url', 'N/A')}\n"
                    f"Date: {item.get('download_date', 'N/A')}\n"
                    f"Saved to: {item.get('directory', 'N/A')}\n"
                    f"{'-' * 50}\n\n"
                )
                history_text.insert("1.0", entry)

        history_text.configure(state="disabled")
        history_window.transient(self)
        history_window.grab_set()


if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.mainloop()
