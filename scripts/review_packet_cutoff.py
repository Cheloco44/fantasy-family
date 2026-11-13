"""Script-only correction cutoff notice; does not approve or publish."""
from review_packet import main

if __name__ == '__main__':
    raise SystemExit(main(['cutoff']))
