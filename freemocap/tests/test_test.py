def returnTrue():
    try:
        return True
    except:
        return False


def test_test():
    assert returnTrue() == True