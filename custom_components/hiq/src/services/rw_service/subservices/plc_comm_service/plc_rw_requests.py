from dataclasses import dataclass


@dataclass()
class PlcRWRequests:
    def __init__(self):
        self._one_byte = {}
        self._two_byte = {}
        self._four_byte = {}
        self._invalid = {}

    @property
    def has_valid(self):
        return (
            len(self._one_byte) == 0
            and len(self._two_byte) == 0
            and len(self._four_byte) == 0
        )

    @property
    def one_byte(self):
        return list(self._one_byte.keys())

    @property
    def two_byte(self):
        return list(self._two_byte.keys())

    @property
    def four_byte(self):
        return list(self._four_byte.keys())

    @property
    def invalid(self):
        return list(self._invalid.keys())

    def add(self, request):
        if request.is_valid:
            self._add_valid(request)
        else:
            self._invalid[request] = True

    def _add_valid(self, request):
        size = request.alc_data.size

        try:
            self._get_valid_dict(size)[request] = True
        except KeyError:
            self._invalid[request] = True

    def _get_valid_dict(self, size):
        if size == 1:
            return self._one_byte
        elif size == 2:
            return self._two_byte
        elif size == 4:
            return self._four_byte
        else:
            raise KeyError

    def __str__(self):
        return f"{len(self.one_byte)}, {len(self.two_byte)}, {len(self.four_byte)} (1B, 2B, 4B)"
