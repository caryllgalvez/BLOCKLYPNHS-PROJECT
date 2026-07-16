from selenium import webdriver


def test_pytest_placeholder():
    assert True


def run_selenium_test():
    driver = webdriver.Chrome()
    try:
        driver.get("https://www.google.com")
        input("Press Enter to close...")
    finally:
        driver.quit()


if __name__ == '__main__':
    run_selenium_test()