# 🎬 MediaHarbor Studio

**A modern, dark-themed YouTube media downloader for desktop.**

MediaHarbor Studio lets you fetch, preview, and download YouTube videos and playlists in your choice of resolution or convert them straight to MP3/M4A/WAV — all through a clean, responsive interface built with Python and CustomTkinter.

![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.9+-yellow)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

- **Paste & Fetch** — drop in a YouTube video or playlist URL and instantly preview the thumbnail, title, channel, duration, views, and resolution
- **Flexible downloads** — choose video quality (up to Best/4K when available) or export audio in MP3, M4A, or WAV
- **Playlist support** — toggle "Whole playlist" to grab an entire playlist in one go
- **Subtitles** — optionally download `.srt` subtitle files alongside your video
- **Embedded thumbnails** — automatically embed the video thumbnail into downloaded files
- **Live progress tracking** — real-time speed, ETA, and downloaded size while a transfer is in progress
- **Custom save location** — pick exactly where downloads are saved, with a one-click "Open Download Folder"
- **Auto-open folder** — optionally open the destination folder as soon as a download completes
- **Download history** — browse all your past downloads from the History tab
- **FFmpeg integration** — automatic detection with a status indicator in the footer
- **Modern dark UI** — a clean, distraction-free interface built for smooth day-to-day use

---

## 📸 Screenshots

| Add a Link | Download in Progress |
|---|---|
| Paste a URL, hit Fetch, and preview your video before downloading | Live speed, ETA, and progress while your file downloads |

| Download Options | Recent Downloads |
|---|---|
| Fine-tune video quality, audio format, subtitles, and save location | Quick access to your most recent downloads with one click |

*(Add your own screenshots to a `/screenshots` folder and reference them here, e.g. `![Home Screen](screenshots/home.png)`)*

---

## 🛠️ Built With

- [Python](https://www.python.org/) — core application logic
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — modern, themeable GUI
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — video/audio extraction and download engine
- [Pillow](https://python-pillow.org/) — thumbnail and image handling
- [FFmpeg](https://ffmpeg.org/) — media processing, format conversion, and merging

---

## 📦 Installation

### Prerequisites
- Python 3.9 or higher
- [FFmpeg](https://ffmpeg.org/download.html) installed and available on your system `PATH`

### Steps

```bash
# Clone the repository
git clone https://github.com/<your-username>/mediaharbor-studio.git
cd mediaharbor-studio

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

> On first launch, MediaHarbor Studio checks for FFmpeg automatically and shows its status (`ffmpeg: detected ✅`) in the footer.

---

## 🚀 Usage

1. Copy a YouTube video or playlist link
2. Paste it into the **Add a link** field and click **Fetch**
3. Review the video preview — title, channel, duration, views, and resolution
4. Configure your **Download Options**:
   - Video quality (e.g. Best)
   - Audio format (MP3 / M4A / WAV)
   - Whole playlist, subtitles, embed thumbnail, auto-open folder
   - Custom save location via **Change**
5. Click **Download Video** or **Download MP3**
6. Track progress in real time, then open the file directly from **Open Download Folder**

---

## 🗂️ Project Structure

```
mediaharbor-studio/
├── main.py                # Application entry point
├── ui/                    # CustomTkinter UI components
├── core/                  # yt-dlp / ffmpeg download & conversion logic
├── assets/                # Icons, logo, and static assets
├── requirements.txt
└── README.md
```

*(Adjust this section to match your actual repo layout.)*

---

## ⚠️ Disclaimer

MediaHarbor Studio is intended for downloading and archiving content you own the rights to, or content that is otherwise permitted for offline use (e.g. Creative Commons, personal backups). Please respect YouTube's [Terms of Service](https://www.youtube.com/t/terms) and copyright law in your jurisdiction.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 👤 Author

**Paramjeet Lamba**

- GitHub: [@your-username](https://github.com/your-username)
- LinkedIn: [Your LinkedIn](https://linkedin.com/in/your-profile)

---

<p align="center">Made with ❤️ using Python & CustomTkinter</p>
