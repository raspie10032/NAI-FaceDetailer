import customtkinter as ctk
from ui.base import BaseScreen
from i18n import t

class HomeScreen(BaseScreen):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        # Title
        label = ctk.CTkLabel(self, text=t("title"), font=ctk.CTkFont(size=30, weight="bold"))
        label.pack(pady=30)

        # Grid container
        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(expand=True, fill="both", padx=50, pady=(0, 50))

        # Tiles
        tiles = [
            (t("tile_token"), t("tile_token_desc"), "Token"),
            (t("tile_t2i"), t("tile_t2i_desc"), "T2I"),
            (t("tile_i2i"), t("tile_i2i_desc"), "I2I"),
            (t("tile_inpaint"), t("tile_inpaint_desc"), "Inpaint"),
            (t("tile_face"), t("tile_face_desc"), "FaceDetailer")
        ]

        for i, (icon, desc, screen_name) in enumerate(tiles):
            row = i // 2
            col = i % 2
            
            tile = ctk.CTkButton(
                grid_frame, 
                text=f"{icon}\n\n{desc}",
                font=ctk.CTkFont(size=16),
                height=150,
                width=300,
                command=lambda name=screen_name: self.controller.show_screen(name)
            )
            tile.grid(row=row, column=col, padx=20, pady=20, sticky="nsew")

        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
