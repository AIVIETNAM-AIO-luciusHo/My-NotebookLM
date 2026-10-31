// --- shuffle array ---
export function shuffleArray(array) {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

// --- single vs multi-choice helpers (the central invariant) ---
// A question is multi-choice iff its correctAnswer is an array with length > 1.
export function isMultiChoice(question) {
    return Array.isArray(question.correctAnswer) && question.correctAnswer.length > 1;
}

// Whether option `idx` is (part of) the correct answer, for either answer shape.
export function isCorrectOption(question, idx) {
    return Array.isArray(question.correctAnswer)
        ? question.correctAnswer.includes(idx)
        : question.correctAnswer === idx;
}

// Whether option `idx` is part of the user's answer, for either answer shape.
export function isOptionChosen(userAnswer, idx) {
    return Array.isArray(userAnswer) ? userAnswer.includes(idx) : userAnswer === idx;
}

// A, B, C, ... label for an option index.
export function optionLabel(index) {
    return String.fromCharCode(65 + index);
}

// --- validate JSON structure ---
export function validateQuizData(data) {
    if (!data.questions || !Array.isArray(data.questions)) {
        return 'Định dạng không hợp lệ: thiếu mảng "questions"';
    }

    for (let i = 0; i < data.questions.length; i++) {
        const q = data.questions[i];

        if (
            typeof q.question !== 'string' ||
            !q.question.trim() ||
            !q.options ||
            !Array.isArray(q.options) ||
            q.correctAnswer === undefined
        ) {
            return `Định dạng câu hỏi không hợp lệ ở vị trí ${i}`;
        }
        if (q.options.length < 2) {
            return `Câu ${i} phải có ít nhất 2 đáp án`;
        }
        if (q.options.some(option => typeof option !== 'string' || !option.trim())) {
            return `Câu ${i} có đáp án không hợp lệ`;
        }

        const isMulti = Array.isArray(q.correctAnswer);
        const isValidAnswerIndex = (idx) =>
            Number.isInteger(idx) && idx >= 0 && idx < q.options.length;

        if (isMulti) {
            if (q.correctAnswer.length === 0) return `Câu ${i} phải có ít nhất một đáp án đúng`;
            const seen = new Set();
            for (let idx of q.correctAnswer) {
                if (!isValidAnswerIndex(idx)) {
                    return `Chỉ số ${idx} trong correctAnswer của câu ${i} không hợp lệ`;
                }
                if (seen.has(idx)) {
                    return `Chỉ số ${idx} bị lặp trong correctAnswer của câu ${i}`;
                }
                seen.add(idx);
            }
        } else {
            // Single choice validation
            if (!isValidAnswerIndex(q.correctAnswer)) {
                return `Chỉ số correctAnswer của câu ${i} không hợp lệ`;
            }
        }
    }

    return null;
}

// --- main processing logic ---
export function processQuizData(data, settings) {
    let processedQuestions = data.questions.map((q, idx) => ({
        ...q,
        originalIndex: idx
    }));

    if (settings.shuffleQuestions) {
        processedQuestions = shuffleArray(processedQuestions);
    }

    if (settings.quizSizeMode === "percentage" && settings.quizSize < 100) {
        const targetCount = Math.max(
            1,
            Math.ceil((settings.quizSize / 100) * processedQuestions.length)
        );
        processedQuestions = processedQuestions.slice(0, targetCount);
    } else if (settings.quizSizeMode === "count") {
        processedQuestions = processedQuestions.slice(0, settings.quizSize);
    }

    processedQuestions = processedQuestions.map((q) => {
        const shouldShuffle = settings.shuffleOptions && q.shuffle !== 0;
        if (!shouldShuffle) return q;

        const optionObjects = q.options.map((opt, idx) => ({
            option: opt,
            originalIndex: idx
        }));

        const shuffled = shuffleArray(optionObjects);

        // Handle remapping for both single (number) and multi (array) answers
        let newCorrectAnswer;
        
        if (Array.isArray(q.correctAnswer)) {
            // Remap all indices for multiple choice and keep them sorted
            newCorrectAnswer = q.correctAnswer.map(oldIdx => 
                shuffled.findIndex(item => item.originalIndex === oldIdx)
            ).sort((a, b) => a - b);
        } else {
            // Standard single choice remapping
            newCorrectAnswer = shuffled.findIndex(
                (item) => item.originalIndex === q.correctAnswer
            );
        }

        return {
            ...q,
            options: shuffled.map((item) => item.option),
            correctAnswer: newCorrectAnswer // Use the new variable
        };
    });

    return { ...data, questions: processedQuestions };
}

// Reads a quiz file, parses it as JSON and validates it. Resolves to
// { data } on success or { error } on parse/validation failure. Shared by the
// upload page and the creator's import. Does not enforce the >= 2 question
// minimum — callers add that where it applies.
// Parse a raw JSON string into validated quiz data. Shared by the file-upload
// path (readQuizFile) and the share-link fetch path so both run the exact same
// validation. Returns { data } or { error }; does not enforce the >= 2 question
// minimum (callers add that where it applies).
export function parseQuizText(text) {
    let data;
    try {
        data = JSON.parse(text);
    } catch {
        return { error: 'Tệp JSON không đúng định dạng' };
    }
    const validationError = validateQuizData(data);
    return validationError ? { error: validationError } : { data };
}

export function readQuizFile(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (event) => resolve(parseQuizText(event.target.result));
        reader.onerror = () => resolve({ error: 'Không đọc được tệp' });
        reader.readAsText(file);
    });
}

// Strips a trailing .json/.txt extension from a quiz name (case-insensitive).
// Used when ingesting a quiz (upload / share import) so the stored display name
// is extension-free — otherwise a later download re-appends one and names pile
// up as "quiz.txt.json.json".
export function stripQuizExtension(name) {
    return (name || '').replace(/\.(json|txt)$/i, '');
}

// Parses the lightweight markup quiz text supports into a structure the
// RichText component renders. Features:
//   - a newline ("\n" in the JSON) splits the text into separate lines, each
//     rendered on its own row (HTML would otherwise collapse the newline);
//   - "**text**" marks an extra-bold run;
//   - "__text__" marks an underlined run.
// Returns an array of lines; each line is an array of { text, bold, underline }
// segments (an empty line is an empty array). Non-string input → a single
// empty line. We parse to plain data (not HTML) so quiz content can never
// inject markup — the component only ever renders text, <strong>, and <u>.
// Bold and underline don't nest: whichever marker opens first wins for that run.
//
// "__text__" only counts at a word boundary (not inside a word: a__b__c, snake__case__x),
// never inside `inline code` or a ``` fenced block. { underline: false } turns __ off
// entirely (the chat renders model text, where a bare __init__ is an identifier).
export function parseRichText(raw, { underline = true } = {}) {
    const text = typeof raw === 'string' ? raw : raw == null ? '' : String(raw);
    let fenced = false;
    return text.split('\n').map((line) => {
        if (/^\s*```/.test(line)) { fenced = !fenced; return [{ text: line, bold: false, underline: false }]; }
        if (fenced) return [{ text: line, bold: false, underline: false }];
        const segments = [];
        // Code spans match first (and are skipped below), so ** / __ inside them stay literal.
        const re = /`[^`\n]*`|\*\*(.+?)\*\*|(?<![\p{L}\p{N}_])__(.+?)__(?![\p{L}\p{N}_])/gu;
        let lastIndex = 0;
        let match;
        while ((match = re.exec(line)) !== null) {
            if (match[1] === undefined && (match[2] === undefined || !underline)) continue;
            if (match.index > lastIndex) {
                segments.push({ text: line.slice(lastIndex, match.index), bold: false, underline: false });
            }
            if (match[1] !== undefined) {
                segments.push({ text: match[1], bold: true, underline: false });
            } else {
                segments.push({ text: match[2], bold: false, underline: true });
            }
            lastIndex = match.index + match[0].length;
        }
        if (lastIndex < line.length) {
            segments.push({ text: line.slice(lastIndex), bold: false, underline: false });
        }
        return segments;
    });
}

// Gom các dòng thành khối: bảng markdown (`| a | b |` + dòng `---`) hoặc đoạn dòng thường.
// Trả dữ liệu thuần (không HTML) nên không thể chèn mã; RichText chỉ map sang <table>/<td>.
const splitRow = (line) => {
    const cells = line.trim().split('|').map((c) => c.trim());
    if (cells[0] === '') cells.shift();
    if (cells.length && cells[cells.length - 1] === '') cells.pop();
    return cells;
};
const isSeparator = (line) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line) && line.includes('-');
const parseCell = (c, o) => parseRichText(c, o)[0];

export function parseRichBlocks(raw, opts) {
    const text = typeof raw === 'string' ? raw : raw == null ? '' : String(raw);
    const lines = text.split('\n');
    const blocks = [];
    let plain = [];
    const flush = () => {
        if (plain.length) blocks.push({ type: 'lines', lines: parseRichText(plain.join('\n'), opts) });
        plain = [];
    };
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('|') && i + 1 < lines.length && lines[i + 1].includes('|') && isSeparator(lines[i + 1])) {
            flush();
            const header = splitRow(lines[i]).map((c) => parseCell(c, opts));
            const rows = [];
            i += 2;
            while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
                rows.push(splitRow(lines[i]).map((c) => parseCell(c, opts)));
                i++;
            }
            i--;
            blocks.push({ type: 'table', header, rows });
        } else {
            plain.push(lines[i]);
        }
    }
    flush();
    return blocks;
}

// Locale date+time for saved-quiz / attempt timestamps. Shared by the library
// and history panes so they format identically.
export function formatTimestamp(ts) {
    return new Date(ts).toLocaleString('vi-VN', { dateStyle: 'medium', timeStyle: 'short' });
}

// Triggers a browser download of the quiz JSON. Content is identical for
// both extensions; only the filename changes.
export function downloadQuizFile(quizData, rawName, extension) {
    const trimmed = (rawName || '').trim();
    // Strip filesystem-forbidden characters; keep spaces/dots so user-typed
    // names look natural after download.
    const safeName = trimmed.replace(/[/\\:*?"<>|]/g, '_') || 'quiz';
    const json = JSON.stringify(quizData, null, 2);
    const mime = extension === 'json' ? 'application/json' : 'text/plain';
    const blob = new Blob([json], { type: mime });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `${safeName}.${extension}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

export function calculateQuestionScore(question, userAnswer) {
    if (userAnswer === undefined || userAnswer === null) return 0;

    // Determine if Multi-choice (Array with >1 correct options)
    const correctArr = Array.isArray(question.correctAnswer) ? question.correctAnswer : [question.correctAnswer];
    const isMulti = correctArr.length > 1;

    if (!isMulti) {
        // --- Single Choice Rule (1 point or 0) ---
        const correctVal = correctArr[0];
        // Handle case where user answer might be wrapped in array or raw value
        const userVal = Array.isArray(userAnswer) ? userAnswer[0] : userAnswer;
        return userVal === correctVal ? 1 : 0;
    } else {
        // --- Multi Choice Rule (F1 Score) ---
        // C = Ground Truth Count
        const C = correctArr.length;
        
        // S = User Selection Count
        const userArr = [...new Set(Array.isArray(userAnswer) ? userAnswer : [userAnswer])];
        const S = userArr.length;

        if (S === 0) return 0;

        // T = True Positives (Intersection)
        // Ensure we compare numbers correctly
        const T = userArr.filter(ans => correctArr.includes(ans)).length;

        const precision = T / S;
        const recall = T / C;

        if (precision + recall === 0) return 0;

        // F1 Formula
        return (2 * precision * recall) / (precision + recall);
    }
}

// Aggregates per-question scores into the result summary. Buckets each question
// as correct (score === 1), incorrect (score === 0), or partial (in between),
// and returns the final score out of 10. `score`/`totalPoints` are numeric;
// callers format for display.
export function summarizeResults(questions, answers) {
    let totalPoints = 0;
    let correctCount = 0;
    let incorrectCount = 0;
    let partialCount = 0;

    questions.forEach((q, idx) => {
        const qScore = calculateQuestionScore(q, answers[idx]);
        totalPoints += qScore;
        if (qScore === 1) correctCount++;
        else if (qScore === 0) incorrectCount++;
        else partialCount++;
    });

    const totalQuestions = questions.length;
    const score = totalQuestions === 0 ? 0 : (totalPoints / totalQuestions) * 10;

    return { correctCount, partialCount, incorrectCount, totalQuestions, totalPoints, score };
}
