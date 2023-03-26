class Slot:
    def __init__(self, id, name, date, start_time, end_time, lesson_name=None):
        self.id = id
        self.date = date
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.lesson_name = lesson_name

    def __eq__(self, other):
        if not isinstance(other, Slot):
            return False

        return self.id == other.id \
               and self.date == other.date \
               and self.name == other.name \
               and self.start_time == other.start_time \
               and self.end_time == other.end_time \
               and self.lesson_name == other.lesson_name
