class UdpActivityService:
    def __init__(self):
        self._rx_count = 0
        self._tx_count = 0

    @property
    def rx_count(self):
        return self._rx_count

    @property
    def tx_count(self):
        return self._tx_count

    def report_rx(self):
        self._rx_count += 1

    def report_tx(self):
        self._tx_count += 1
