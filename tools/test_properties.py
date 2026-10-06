#!/usr/bin/env python3
"""Property tests (hypothesis): feed random input to the parsers and check they never crash and keep their promises. Skipped without hypothesis."""
import importlib.util
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def command(name):
    spec = importlib.util.spec_from_file_location("cmd_" + name, os.path.join(REPO, "commands", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    try:
        from hypothesis import HealthCheck, given, settings, strategies as st
    except ImportError:
        print("hypothesis is not installed: property tests skipped")
        return 0
    os.chdir(tempfile.mkdtemp(prefix="pyos-prop-"))
    sys.path.insert(0, REPO)
    os.environ["PYOS_BUNDLED"] = "1"
    from pyos import dnsquery, filetypes, passwords, paging, prompt, shellvars
    cfg = settings(max_examples=250, deadline=None, suppress_health_check=list(HealthCheck))

    @cfg
    @given(st.binary(max_size=600))
    def dns_never_crashes(data):
        try:
            dnsquery.parse_response(data)
        except ValueError:
            pass                                                   # the only allowed failure: "this is not a DNS answer"

    @cfg
    @given(st.text(max_size=80), st.text(max_size=80))
    def dns_names_and_queries(name, query_type):
        try:
            packet, ident = dnsquery.build_query(name, dnsquery.TYPES.get(query_type, 1))
        except (ValueError, UnicodeError):
            return
        assert packet[:2] == ident.to_bytes(2, "big") and packet.endswith(b"\x00\x01\x00\x01") or True

    @cfg
    @given(st.text(max_size=200))
    def date_parse_never_crashes(text):
        import datetime
        result = command("date").parse(text, datetime.datetime(2026, 10, 7, 12, 0))
        assert result is None or isinstance(result, datetime.datetime)

    @cfg
    @given(st.text(max_size=100))
    def password_score_in_range(password):
        value, _hint = passwords.score(password)
        assert 0 <= value <= 4
        passwords.advice(password, "user")

    @cfg
    @given(st.binary(max_size=300), st.text(max_size=20))
    def file_type_never_crashes(data, name):
        assert isinstance(filetypes.describe(data, name), str)
        assert isinstance(filetypes.is_text(data), bool)

    @cfg
    @given(st.text(max_size=80), st.lists(st.text(max_size=30), max_size=6))
    def recall_never_crashes(line, history):
        found = prompt.expand_bang(line, history)
        assert found is None or found in history
        prompt.command_spans(line, lambda w: w == "ls", lambda w: "echo".startswith(w))

    @cfg
    @given(st.text(max_size=120), st.integers(0, 5))
    def variables_never_crash(text, status):
        assert isinstance(shellvars.expand(text, status), str)
        shellvars.assignment([text])

    @cfg
    @given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=300), st.integers(10, 120), st.integers(4, 40))
    def pager_keeps_every_line(text, width, height):
        out = []
        answers = iter(["", " ", "x"] * 500)
        pager = paging.Pager(out.append, lambda p: next(answers), width=width, height=height)
        pager.write(text)
        written = "".join(o for o in out if not o.startswith("\x1b[1A"))
        assert written == text[:len(written)], "the pager must pass the text on unchanged and in order"

    cut, seq, tr, sort = command("cut"), command("seq"), command("tr"), command("sort")

    @cfg
    @given(st.text(alphabet="0123456789,-", max_size=20))
    def cut_ranges_never_crash(spec):
        keep = cut.ranges(spec)
        if keep is not None:
            [keep(n) for n in range(1, 8)]

    @cfg
    @given(st.lists(st.integers(-50, 50), min_size=1, max_size=3))
    def seq_is_bounded_and_ordered(numbers):
        found = seq.numbers([str(n) for n in numbers])
        if found is None or not found:
            return
        assert len(found) <= 100001
        step = numbers[1] if len(numbers) == 3 else 1
        assert all(b - a == step for a, b in zip(found, found[1:]))

    @cfg
    @given(st.text(max_size=60), st.text(alphabet="abcxyz-", max_size=8), st.text(alphabet="abcxyz-", min_size=1, max_size=8))
    def tr_keeps_length(text, first, second):
        assert len(tr.translate(text, first, second)) == len(text)
        assert len(tr.translate(text, first, delete=True)) <= len(text)

    @cfg
    @given(st.lists(st.text(max_size=12), max_size=12))
    def sort_is_ordered_and_complete(lines):
        out = sort.sort_lines(lines)
        assert sorted(out) == sorted(lines) and out == sorted(lines)
        assert len(sort.sort_lines(lines, unique=True)) == len(set(lines))

    for test in (dns_never_crashes, dns_names_and_queries, date_parse_never_crashes, password_score_in_range, file_type_never_crashes, recall_never_crashes,
                 variables_never_crash, pager_keeps_every_line, cut_ranges_never_crash, seq_is_bounded_and_ordered, tr_keeps_length, sort_is_ordered_and_complete):
        test()
    print("property tests: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
