def test_env_check_reports_a_status(check_env, capsys):
    code = check_env.main()
    out = capsys.readouterr().out
    assert "ADII environment check" in out
    assert code in (0, 1)          # informative either way; CI asserts 0
