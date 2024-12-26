import multiprocessing
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import ffmpeg
from tqdm import tqdm  # For progress bar


class AudioSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Sync Tool")
        self.root.geometry("600x500")
        self.root.config(bg="#333333")

        # Variables to store file paths
        self.video_file = ""
        self.audio_file = ""

        # Modern fonts
        self.font_large = ("Helvetica Neue", 16, "bold")
        self.font_small = ("Helvetica Neue", 12)

        # UI Elements
        self.create_widgets()

    def create_widgets(self):
        # Header
        header = tk.Label(
            self.root,
            text="🎧 Audio Sync Tool 🎬",
            font=("Helvetica Neue", 24, "bold"),
            fg="#ffffff",
            bg="#333333",
        )
        header.pack(pady=30)

        # Video Selection
        video_card = self.create_card("Select Video File", self.select_video)
        video_card.pack(pady=10)

        self.video_label = tk.Label(
            self.root,
            text="No video selected",
            fg="#888888",
            font=self.font_small,
            bg="#333333",
        )
        self.video_label.pack()

        # Audio Selection
        audio_card = self.create_card("Select Audio File", self.select_audio)
        audio_card.pack(pady=10)

        self.audio_label = tk.Label(
            self.root,
            text="No audio selected",
            fg="#888888",
            font=self.font_small,
            bg="#333333",
        )
        self.audio_label.pack()

        # Audio Offset
        offset_frame = tk.Frame(self.root, bg="#333333")
        tk.Label(
            offset_frame,
            text="Audio Offset (seconds):",
            fg="#ffffff",
            font=self.font_small,
            bg="#333333",
        ).pack(side=tk.LEFT, padx=10)
        self.offset_entry = tk.Entry(
            offset_frame,
            width=10,
            font=self.font_small,
            bg="#444444",
            fg="#ffffff",
            bd=0,
            insertbackground="white",
        )
        self.offset_entry.insert(0, "0")
        self.offset_entry.pack(side=tk.LEFT)
        offset_frame.pack(pady=20)

        # Replace Audio Button
        replace_button = tk.Button(
            self.root,
            text="Replace Audio",
            command=self.start_replace_audio,
            font=self.font_large,
            fg="#ffffff",
            bg="#00bcd4",
            relief="flat",
            activebackground="#009688",
        )
        replace_button.pack(pady=30, padx=50, ipadx=20, ipady=10)

    def create_card(self, text, command):
        card = tk.Frame(
            self.root, bg="#444444", bd=0, relief="solid", width=300, height=60
        )
        card.grid_propagate(False)
        card.config(cursor="hand2")
        button = tk.Button(
            card,
            text=text,
            command=command,
            font=self.font_small,
            fg="#ffffff",
            bg="#00bcd4",
            relief="flat",
            activebackground="#009688",
            width=20,
        )
        button.pack(expand=True)
        return card

    def select_video(self):
        file = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("MKV Files", "*.mkv"), ("All Files", "*.*")],
        )
        if file:
            self.video_file = file
            self.video_label.config(text=os.path.basename(file), fg="#ffffff")

    def select_audio(self):
        file = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[("EAC3/AC3 Audio Files", "*.eac3;*.ac3"), ("All Files", "*.*")],
        )
        if file:
            self.audio_file = file
            self.audio_label.config(text=os.path.basename(file), fg="#ffffff")

    def start_replace_audio(self):
        threading.Thread(target=self.replace_audio).start()

    def replace_audio(self):
        if not self.video_file or not self.audio_file:
            messagebox.showerror(
                "Error", "Please select both a video and an audio file."
            )
            return

        # Extract the output name based on the input video file
        base_name = os.path.splitext(os.path.basename(self.video_file))[0]
        output_name = f"{base_name}_audio_replaced.mkv"

        try:
            # Retrieve audio offset from user input (allow negative values)
            offset = float(self.offset_entry.get())
            temp_audio_file = "temp_audio_adjusted.eac3"

            # Step 1: Adjust audio timing based on the offset (both positive and negative)
            if offset != 0:
                if offset < 0:
                    # Shorten the audio for negative offsets (trim the first few seconds)
                    ffmpeg.input(self.audio_file, ss=abs(offset)).output(
                        temp_audio_file
                    ).run(overwrite_output=True)
                else:
                    # Apply the delay for positive offsets by adding silence
                    ffmpeg.input(self.audio_file).output(
                        temp_audio_file,
                        af=f"adelay={int(offset * 1000)}|{int(offset * 1000)}",
                    ).run(overwrite_output=True)
            else:
                # No offset, just copy the audio
                ffmpeg.input(self.audio_file).output(temp_audio_file).run(
                    overwrite_output=True
                )

            # Step 2: Replace audio in the video and use H.265 encoding for the video
            output_kwargs = {
                "vcodec": self.get_gpu_options()[
                    "vcodec"
                ],  # GPU-based encoding for video
                "acodec": "eac3",  # Re-encode the audio with eac3 codec (or aac)
                "crf": 28,  # Constant Rate Factor for quality control (lower is better)
                "threads": multiprocessing.cpu_count(),  # Use all available CPU cores
                **self.get_gpu_options(),  # Include GPU encoding options
            }

            # Use tqdm for a progress bar during the process
            with tqdm(
                total=100,
                desc="Processing",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed} < {remaining}, {rate_fmt}]",
            ) as pbar:
                ffmpeg.concat(
                    ffmpeg.input(self.video_file),
                    ffmpeg.input(temp_audio_file),
                    v=1,  # One video stream
                    a=1,  # One audio stream
                ).output(
                    output_name,
                    **output_kwargs,  # Unpack the GPU encoding options into the output
                ).run(
                    overwrite_output=True,
                    capture_stdout=True,
                    capture_stderr=True,
                )

                # For example, increase progress bar after each output
                pbar.update(100)

            # Cleanup: Remove temporary audio file
            os.remove(temp_audio_file)

            messagebox.showinfo(
                "Success",
                f"Audio replaced successfully with sync!\nSaved as {output_name}",
            )

        except ffmpeg.Error as e:
            messagebox.showerror(
                "Error",
                f"FFmpeg error occurred:\n{e.stderr.decode() if e.stderr else e}",
            )
        except ValueError:
            messagebox.showerror(
                "Error", "Invalid offset value. Please enter a numeric value."
            )

    def get_gpu_options(self):
        # Set GPU encoding options based on system capabilities (for NVIDIA, AMD, or Intel)
        if os.environ.get(
            "CUDA_VISIBLE_DEVICES"
        ):  # Check if CUDA (NVIDIA) is available
            return {
                "vcodec": "hevc_nvenc",  # Use NVIDIA's NVENC for HEVC (H.265) encoding
                "preset": "p1",  # Max quality preset for NVENC
                "tune": "lossless",  # Use lossless encoding
                "cq": "0",  # Lossless quality (lower is better)
                "rc": "vbr_hq",  # High-quality variable bitrate
                "gpu": "0",  # Specify the first GPU (can be changed for multiple GPUs)
            }
        elif "VCE" in os.environ:  # Check if AMD VCE is available
            return {
                "vcodec": "hevc_amf",  # Use AMD's AMF for HEVC encoding
                "preset": "quality",  # High-quality preset for AMD
                "tune": "lossless",  # Lossless quality
            }
        elif "VAAPI" in os.environ:  # Check if Intel VAAPI is available
            return {
                "vcodec": "hevc_vaapi",  # Use Intel's VAAPI for HEVC encoding
                "preset": "ultrafast",  # Max speed while keeping good quality
            }
        else:
            # Fallback for no GPU detected: Use software encoding
            return {
                "vcodec": "libx265",  # Use x265 (software) for HEVC encoding
                "preset": "ultrafast",  # Max speed
                "crf": "28",  # Constant Rate Factor for quality
            }


# Running the app
root = tk.Tk()
app = AudioSyncApp(root)
root.mainloop()
