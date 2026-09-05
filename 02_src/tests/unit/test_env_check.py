from scripts_check_env_shim import check_env


def test_env_check_reports_a_status(capsys):
    code = check_env.main()
    out = capsys.readouterr().out
    assert "ADII environment check" in out
    assert code in (0, 1)          # informative either way; CI asserts 0
