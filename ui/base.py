import customtkinter as ctk

class BaseScreen(ctk.CTkFrame):
    def __init__(self, parent, controller, **kwargs):
        kwargs.setdefault("fg_color", ("#f5f5f5", "#0f0f0f"))
        super().__init__(parent, **kwargs)
        self.controller = controller
        self.config = getattr(controller, 'config', {})

    def on_show(self):
        pass