class Memory:
    remember: bool = True
    what: str = ""

    def get_memory(self):
        if self.what and self.remember:
            return f"Remember, you last said {self.what}\n"
        else:
            return ""