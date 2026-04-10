def normalize_ph(ph):

    if 6 <= ph <= 7.5:
        return 1
    elif 5 <= ph < 6 or 7.5 < ph <= 8.5:
        return 0.7
    else:
        return 0.3


def normalize_n(n):

    if n > 0.5:
        return 1
    elif n > 0.2:
        return 0.7
    else:
        return 0.3


def normalize_soc(soc):

    if soc > 1:
        return 1
    elif soc > 0.5:
        return 0.7
    else:
        return 0.3


def normalize_cec(cec):
    if cec > 25:
        return 1
    elif cec > 10:
        return 0.7
    else:
        return 0.3


def normalize_bd(bd):
    if bd < 1.3:
        return 1
    elif bd < 1.6:
        return 0.7
    else:
        return 0.3


