class Slot:
    def __init__(self, id, name, start_time, end_time, id_enc=None, booking_progress_enc=None):
        self.id = id
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.lesson_name = None
        self.type = None

        # required for booking
        self.id_enc = id_enc
        self.booking_progress_enc = booking_progress_enc

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
        return f"{self.start_time.strftime('%d %b %Y %H:%M')} \t {self.lesson_name}"
