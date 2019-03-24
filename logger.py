import logging

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(asctime)s - %(message)s'))

log = logging.getLogger('nbot')
log.setLevel(logging.DEBUG)
log.addHandler(console_handler)
