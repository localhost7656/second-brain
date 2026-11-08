"""Offline multilingual regression checks. No real model is exercised."""
import re
import tempfile
import unittest
from pathlib import Path

import yaml
from brain import config, ingest, llm, phase2, prompts, util
from brain.embed import _fake_vec

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [
    ('Сад', 'Посадить помидоры и поливать каждый вечер.'),
    ('Jardín', 'Plantar tomates y regar cada tarde.'),
    ('庭', '庭にトマトを植えて毎晩水をやる。'),
    ('حديقة', 'زرع الطماطم وسقيها كل مساء.'),
]

class MultilingualTests(unittest.TestCase):
    def test_prompts_have_policy_and_keep_variables(self):
        files = list((ROOT / 'prompts').glob('*.md'))
        self.assertEqual(len(files), 11)
        for path in files:
            text = path.read_text(encoding='utf-8')
            self.assertIn('language of the relevant source notes', text, path.name)
            self.assertIn('Never translate fixed JSON keys', text, path.name)
            self.assertNotIn('exclusively in English', text, path.name)
            vars = set(re.findall(r'\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}', text))
            cfg = config.Config({}, ROOT / 'settings.yaml')
            rendered = prompts.render(cfg, path.stem, {k: 'пример 日本語' for k in vars})
            self.assertNotRegex(rendered, r'\{\{\s*[a-z_]+\s*\}\}')
            if vars: self.assertIn('пример 日本語', rendered)

    def test_utf8_files_and_frontmatter_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            for title, text in EXAMPLES:
                p = Path(tmp) / (util.safe_name(title) + '.md')
                util.write_md(p, {'title': title}, text)
                metadata, body = util.read_md(p)
                self.assertEqual(metadata['title'], title)
                self.assertIn(text, body)
                raw, encoding = ingest.read_text_file(p)
                self.assertIn(text, raw)
                self.assertEqual(encoding, 'utf-8')

    def test_json_and_document_protocol_preserve_text(self):
        for title, text in EXAMPLES:
            parsed = llm.extract_json('{"text": ' + __import__('json').dumps(text, ensure_ascii=False) + '}')
            self.assertEqual(parsed['text'], text)
            response = '=== FILE: Summary ===\n# ' + title + '\n\n' + text * 2 + '\n\n=== FILE: ' + title + ' ===\n' + text * 2
            self.assertEqual(phase2._validate_synth(response), [])
            self.assertEqual(phase2.parse_files(response)[1][0], title)
            self.assertIn(text, phase2.parse_files(response)[0][1])

    def test_fake_vectors_include_non_english_words(self):
        for _, text in EXAMPLES:
            self.assertGreater(float((_fake_vec(text) ** 2).sum()), 0)

    def test_date_headings_and_invalid_dates(self):
        for heading in ("12.03.2021", "12.03.2021 г.", "2021-03-12", "12 March 2021", "пятница, 12 марта 2021 года в 15:30"):
            markers = ingest.find_date_markers([heading])
            self.assertEqual(markers[0]["date"], "2021-03-12", heading)
        self.assertEqual(ingest.find_date_markers(["31.02.2021"]), [])

    def test_legacy_russian_frontmatter_is_understood(self):
        result = ingest.parse_header("---\nдата: 2021-03-12\nподсказка: Сад\n---\n\nТекст")
        self.assertEqual(result["date"], "2021-03-12")
        self.assertEqual(result["hint"], "Сад")
        self.assertEqual(result["body"].strip(), "Текст")

    def test_all_configured_dialogue_markers_reach_the_model(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from brain import pipeline
        cfg = MagicMock()
        cfg.markers.return_value = (["Me:", "Yo:"], ["AI:", "IA:"])
        cfg.source_shift.return_value = 0
        entity = SimpleNamespace(container_id="c1", fm={}, compact=None, text="Yo: idea", work_text="Yo: idea", created="2021-03-12", title="Note", id="e1")
        ctx = SimpleNamespace(cfg=cfg, w=MagicMock(), llm=MagicMock(), logs=MagicMock(), thr=MagicMock(return_value=0), count=MagicMock())
        ctx.llm.text.return_value = "idea"
        with patch.object(pipeline, "_cls", return_value={"noise": 1, "compaction_logged": True}), patch.object(pipeline.ops, "set_stage"):
            pipeline.step_compact(ctx, entity)
        sent = ctx.llm.text.call_args.args[1]
        for token in ("Me:", "Yo:"):
            self.assertIn(token, sent["user_markers"])
        for token in ("AI:", "IA:"):
            self.assertIn(token, sent["ai_markers"])
        ctx.w.nodes = {"c1": SimpleNamespace(title="Topic", description="")}
        ctx.llm.json.side_effect = RuntimeError("captured")
        with patch.object(pipeline, "_drop_leftovers"), self.assertRaisesRegex(RuntimeError, "captured"):
            pipeline.step_extract(ctx, entity)
        sent = ctx.llm.json.call_args.args[1]
        for token in ("Me:", "Yo:"):
            self.assertIn(token, sent["user_markers"])
        for token in ("AI:", "IA:"):
            self.assertIn(token, sent["ai_markers"])
        for name in ("Compaction", "Extraction"):
            template = (ROOT / "prompts" / (name + ".md")).read_text(encoding="utf-8")
            values = {k: "test" for k in re.findall(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}", template)}
            values.update(user_markers=sent["user_markers"], ai_markers=sent["ai_markers"])
            rendered = prompts.render(config.Config({}, ROOT / "settings.yaml"), name, values)
            self.assertIn("Yo:", rendered)
            self.assertIn("IA:", rendered)

    def test_classification_receives_all_dialogue_markers_on_both_paths(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from brain import classify, ondemand
        cfg = MagicMock()
        cfg.markers.return_value = (["Me:", "Yo:"], ["AI:", "IA:"])
        ctx = SimpleNamespace(cfg=cfg, w=MagicMock(), llm=MagicMock(), progress=MagicMock())
        ctx.llm.json.side_effect = RuntimeError("captured")
        item = {"date": "2021-03-12", "source": "", "name": "note", "mode": "steady_state"}
        with patch.object(classify, "load_item_paragraphs", return_value=["Yo: idea"]), \
             patch.object(classify, "input_limit", return_value=100000), \
             patch.object(classify, "containers_for_prompt", return_value=[]), \
             self.assertRaisesRegex(RuntimeError, "captured"):
            classify.classify_item(ctx, item)
        first = ctx.llm.json.call_args.args[1]
        e = SimpleNamespace(title="Note", work_text="Yo: idea", created="2021-03-12", fm={})
        ctx.w.state = {}; ctx.w.entities = {"e1": e}
        with patch.object(ondemand, "containers_for_prompt", return_value=[]), \
             self.assertRaisesRegex(RuntimeError, "captured"):
            ondemand.revalidate(ctx, None, ["e1"])
        second = ctx.llm.json.call_args.args[1]
        for values in (first, second):
            for token in ("Me:", "Yo:"): self.assertIn(token, values["user_markers"])
            for token in ("AI:", "IA:"): self.assertIn(token, values["ai_markers"])
            rendered = prompts.render(config.Config({}, ROOT / "settings.yaml"), "Classification", values)
            self.assertIn("Yo:", rendered); self.assertIn("IA:", rendered)

    def test_checkbox_markers(self):
        from brain.questions import CHECK
        for mark in ("x", "X", "х", "Х", "✓", "v", "V"):
            self.assertIsNotNone(CHECK.match("- [" + mark + "] option"), mark)

    def test_default_styles_are_not_english_only(self):
        self.assertIn('language of the source material', config.DEFAULTS['style']['global'])
        names = ['settings.template.yaml'] + (['settings.yaml'] if (ROOT / 'settings.yaml').exists() else [])
        for name in names:
            data = yaml.safe_load((ROOT / name).read_text(encoding='utf-8'))
            self.assertIn('language of the source material', data['style']['global'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
