
def normalize_answer_mode(mode):
    if mode in ['quick','lite']:
        return 'normal'
    return mode
