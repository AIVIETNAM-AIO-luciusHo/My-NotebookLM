import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRichText } from '../../src/utils/utils.js';

test('parseRichText returns a single plain line for plain text', () => {
  assert.deepEqual(parseRichText('hello world'), [
    [{ text: 'hello world', bold: false, underline: false }],
  ]);
});

test('parseRichText splits on newlines into separate lines', () => {
  assert.deepEqual(parseRichText('line one\nline two'), [
    [{ text: 'line one', bold: false, underline: false }],
    [{ text: 'line two', bold: false, underline: false }],
  ]);
});

test('parseRichText represents a blank line as an empty segment array', () => {
  assert.deepEqual(parseRichText('a\n\nb'), [
    [{ text: 'a', bold: false, underline: false }],
    [],
    [{ text: 'b', bold: false, underline: false }],
  ]);
});

test('parseRichText marks __text__ as an underlined segment', () => {
  assert.deepEqual(parseRichText('see __this__ word'), [
    [
      { text: 'see ', bold: false, underline: false },
      { text: 'this', bold: false, underline: true },
      { text: ' word', bold: false, underline: false },
    ],
  ]);
});

test('parseRichText marks **text** as a bold segment', () => {
  assert.deepEqual(parseRichText('see **this** word'), [
    [
      { text: 'see ', bold: false, underline: false },
      { text: 'this', bold: true, underline: false },
      { text: ' word', bold: false, underline: false },
    ],
  ]);
});

test('parseRichText handles bold and underline in the same line', () => {
  assert.deepEqual(parseRichText('**bold** and __under__'), [
    [
      { text: 'bold', bold: true, underline: false },
      { text: ' and ', bold: false, underline: false },
      { text: 'under', bold: false, underline: true },
    ],
  ]);
});

test('parseRichText handles multiple underlines and underline at the edges', () => {
  assert.deepEqual(parseRichText('__a__ and __b__'), [
    [
      { text: 'a', bold: false, underline: true },
      { text: ' and ', bold: false, underline: false },
      { text: 'b', bold: false, underline: true },
    ],
  ]);
});

test('parseRichText parses markup within each line independently', () => {
  assert.deepEqual(parseRichText('**top**\nbottom'), [
    [{ text: 'top', bold: true, underline: false }],
    [{ text: 'bottom', bold: false, underline: false }],
  ]);
});

test('parseRichText leaves a lone/unclosed marker as literal text', () => {
  assert.deepEqual(parseRichText('a __ b'), [[{ text: 'a __ b', bold: false, underline: false }]]);
  assert.deepEqual(parseRichText('__unclosed'), [[{ text: '__unclosed', bold: false, underline: false }]]);
  assert.deepEqual(parseRichText('**unclosed'), [[{ text: '**unclosed', bold: false, underline: false }]]);
});

test('parseRichText does not bold/underline empty markers', () => {
  // /__(.+?)__/ and /\*\*(.+?)\*\*/ both require at least one char between markers.
  assert.deepEqual(parseRichText('x ____ y'), [[{ text: 'x ____ y', bold: false, underline: false }]]);
  assert.deepEqual(parseRichText('x **** y'), [[{ text: 'x **** y', bold: false, underline: false }]]);
});

test('parseRichText coerces non-string input to a single empty line', () => {
  assert.deepEqual(parseRichText(null), [[]]);
  assert.deepEqual(parseRichText(undefined), [[]]);
  assert.deepEqual(parseRichText(''), [[]]);
});

import { parseRichBlocks } from '../../src/utils/utils.js';

test('parseRichBlocks: bảng markdown thành khối table, không có HTML thô', () => {
  const b = parseRichBlocks('Mở đầu\n| Tên | Giá |\n| --- | :---: |\n| **A** | 1 |\n| B | <b>2</b> |\nKết');
  assert.equal(b.length, 3);
  assert.equal(b[0].type, 'lines');
  assert.equal(b[1].type, 'table');
  assert.deepEqual(b[1].header.map((c) => c[0].text), ['Tên', 'Giá']);
  assert.equal(b[1].rows.length, 2);
  assert.deepEqual(b[1].rows[0][0], [{ text: 'A', bold: true, underline: false }]);
  assert.equal(b[1].rows[1][1][0].text, '<b>2</b>'); // giữ nguyên là văn bản; React sẽ escape
  assert.equal(b[2].type, 'lines');
});

test('parseRichBlocks: không có dòng --- thì không phải bảng; thiếu | ở đầu/cuối vẫn nhận', () => {
  assert.deepEqual(parseRichBlocks('a | b\nc | d').map((x) => x.type), ['lines']);
  const b = parseRichBlocks('x | y\n--- | ---\n1 | 2');
  assert.equal(b[0].type, 'table');
  assert.deepEqual(b[0].rows[0].map((c) => c[0].text), ['1', '2']);
});

// L1: __x__ chỉ là gạch chân ở ranh giới từ, không trong từ / code; chat tắt hẳn.
const plain = (t) => [[{ text: t, bold: false, underline: false }]];
test('parseRichText: __ trong từ không phải gạch chân', () => {
  assert.deepEqual(parseRichText('a__b__c'), plain('a__b__c'));
  assert.deepEqual(parseRichText('snake_case_name và my__var__x'), plain('snake_case_name và my__var__x'));
});
test('parseRichText: __init__ trong inline code và khối ``` giữ nguyên', () => {
  assert.deepEqual(parseRichText('dùng `__init__` và `__x__`'), plain('dùng `__init__` và `__x__`'));
  const r = parseRichText('```\n__init__\n```');
  assert.ok(r.every((l) => l.every((s) => !s.underline)));
});
test('parseRichText: __đậm__ thật vẫn gạch chân, kể cả cạnh code', () => {
  assert.deepEqual(parseRichText('xem __đậm__ ok'), [[
    { text: 'xem ', bold: false, underline: false },
    { text: 'đậm', bold: false, underline: true },
    { text: ' ok', bold: false, underline: false },
  ]]);
  assert.ok(parseRichText('`__a__` __b__')[0].some((s) => s.underline && s.text === 'b'));
});
test('parseRichText: underline:false (chat) để __init__ trần nguyên văn, ** vẫn đậm', () => {
  assert.deepEqual(parseRichText('class có __init__ ở đây', { underline: false }), plain('class có __init__ ở đây'));
  assert.equal(parseRichText('**a** __b__', { underline: false })[0][0].bold, true);
});
