class Slot:
    def __init__(self, id, name, start_time, end_time, lesson_name=None, lesson_type=None):
        self.id = id
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.lesson_name = lesson_name
        self.type = lesson_type

    def __eq__(self, other):
        if not isinstance(other, Slot):
            return False

        return self.id == other.id \
               and self.name == other.name \
               and self.start_time == other.start_time \
               and self.end_time == other.end_time \
               and self.lesson_name == other.lesson_name

    def __hash__(self):
        return hash((self.id, self.name, self.start_time, self.end_time, self.lesson_name))

    def __str__(self):
        return f"{self.lesson_name} {self.start_time.strftime('%d %b %Y %H:%M')}"
