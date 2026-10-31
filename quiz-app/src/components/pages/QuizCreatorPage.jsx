import { useEffect, useRef, useState } from 'react';
import QuestionEditor from '../ui/QuestionEditor';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import ErrorBanner from '../ui/ErrorBanner';
import Pagination from '../ui/Pagination';
import { downloadQuizFile, readQuizFile } from '../../utils/utils';
import { useTheme } from '../../contexts/useTheme';
import { useBackGuard } from '../../hooks/useBackGuard';
import { buildQuizPayload, emptyQuestion, quizToCreatorQuestions } from '../../utils/quizCreator';

const stripExtension = (name) => name.replace(/\.(json|txt)$/i, '');

const QuizCreatorPage = ({ setView, editingQuiz = null, setEditingQuiz, onSaveEdit, editHasHistory = false }) => {
  const { isDarkMode, classes } = useTheme();
  const isEditing = Boolean(editingQuiz);
  // In edit mode, seed the editor from the saved quiz; otherwise start blank.
  const [questions, setQuestions] = useState(() =>
    editingQuiz ? quizToCreatorQuestions(editingQuiz.rawData) : [emptyQuestion(), emptyQuestion()]
  );
  const [filename, setFilename] = useState(() =>
    editingQuiz ? stripExtension(editingQuiz.name) : 'my-quiz'
  );
  const [error, setError] = useState('');
  const [showExitModal, setShowExitModal] = useState(false);
  // Questions parsed from an upload, held until the user confirms replacing
  // their current work. null when no import is awaiting confirmation.
  const [pendingImport, setPendingImport] = useState(null);
  // When saving an edit to a quiz that has results history, confirm first: the
  // content (and id) change means past attempts can no longer be reviewed.
  const [showHistoryWarn, setShowHistoryWarn] = useState(false);
  const importInputRef = useRef(null);

  // Entering the creator should start at the top, not inherit the upload
  // page's scroll position (which lands the editor mid-screen).
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  // Paginate the question editors 10 per page; the actions box below stays put.
  const PER_PAGE = 10;
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(questions.length / PER_PAGE));
  // Clamp so removing questions on the last page can't strand us past the end.
  const currentPage = Math.min(page, totalPages - 1);

  const addQuestion = () => {
    // Jump to the page the new (appended) question lands on.
    setPage(Math.floor(questions.length / PER_PAGE));
    setQuestions((prev) => [...prev, emptyQuestion()]);
  };

  const updateQuestion = (idx, updated) => {
    setQuestions((prev) => prev.map((q, i) => (i === idx ? updated : q)));
  };

  const removeQuestion = (idx) => {
    if (questions.length <= 1) return;
    setQuestions((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleDownload = (extension) => {
    const result = buildQuizPayload(questions);
    if (result.error) {
      setError(result.error);
      return;
    }
    setError('');
    downloadQuizFile(result.data, filename, extension);
  };

  // Save edits back to the library (App handles persistence + navigation).
  const performSaveEdit = () => {
    const result = buildQuizPayload(questions);
    setShowHistoryWarn(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setError('');
    onSaveEdit(result.data, filename.trim() || editingQuiz.name);
  };

  const handleSaveEdit = () => {
    // Validate up front so we don't warn about history only to fail the build.
    const result = buildQuizPayload(questions);
    if (result.error) {
      setError(result.error);
      return;
    }
    setError('');
    // Only warn when the user actually changed something — an untouched edit
    // keeps the same content id, so its history stays intact.
    if (editHasHistory && isDirty) {
      setShowHistoryWarn(true);
      return;
    }
    performSaveEdit();
  };

  // Snapshot the editor's initial contents on first render so we can tell
  // whether the user has actually changed anything. In edit mode the form
  // starts pre-filled, so a plain "has content" check is always true and can't
  // distinguish unsaved edits from an untouched quiz.
  const initialSnapshot = useRef(null);
  if (initialSnapshot.current === null) {
    initialSnapshot.current = JSON.stringify({ questions, filename });
  }
  const isDirty = JSON.stringify({ questions, filename }) !== initialSnapshot.current;

  const handleImport = async (e) => {
    const file = e.target.files[0];
    // Reset the input so re-selecting the same file fires onChange again.
    e.target.value = '';
    if (!file) return;

    const { data, error: parseError } = await readQuizFile(file);
    if (parseError) {
      setError(parseError);
      return;
    }
    setError('');
    const imported = quizToCreatorQuestions(data);
    // Guard against silently discarding unsaved changes.
    if (isDirty) setPendingImport(imported);
    else setQuestions(imported);
  };

  const confirmImport = () => {
    setQuestions(pendingImport);
    setPendingImport(null);
  };

  const requestExit = () => {
    if (isDirty) setShowExitModal(true);
    else {
      setEditingQuiz(null);
      setView('upload');
    }
  };

  const confirmExit = () => {
    setShowExitModal(false);
    setEditingQuiz(null);
    setView('upload');
  };

  // Mobile/browser Back behaves like the on-screen "Back to Upload" button
  // (confirms first if there is unsaved work) instead of leaving the app.
  useBackGuard(requestExit);

  return (
    <div className="min-h-screen p-4">
      <div className="max-w-4xl mx-auto py-8">
        <div className="mb-4 flex flex-wrap gap-3 sticky top-4 z-20">
          <button
            type="button"
            onClick={requestExit}
            className={`px-4 py-2 shadow-lg ${
              isDarkMode ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-600 hover:bg-gray-700'
            } text-white rounded-lg font-medium transition-all`}
            title="Về trang tải lên"
          >
            Về trang tải lên
          </button>
          {isEditing && isDirty && (
            // Reuses the (edit-mode-empty) import slot so changes can be saved
            // without scrolling down to the bottom Save Changes button.
            <button
              type="button"
              onClick={handleSaveEdit}
              className="px-4 py-2 shadow-lg bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-all"
              title="Lưu thay đổi và về trang tải lên"
            >
              Lưu thay đổi
            </button>
          )}
          {!isEditing && (
            <>
              <button
                type="button"
                onClick={() => importInputRef.current?.click()}
                className="px-4 py-2 shadow-lg bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-all"
                title="Tải lên một bài quiz có sẵn để sửa"
              >
                Tải lên quiz của bạn
              </button>
              <input
                ref={importInputRef}
                type="file"
                accept=".json,.txt"
                onChange={handleImport}
                className="hidden"
              />
            </>
          )}
        </div>

        <div className={`${classes.cardBg} rounded-2xl shadow-2xl p-6 sm:p-8`}>
          <div className="mb-6">
            <h1 className={`text-3xl font-bold ${classes.textColor} mb-2`}>
              {isEditing ? 'Sửa quiz' : 'Tạo quiz'}
            </h1>
            <p className={classes.mutedText}>
              {isEditing
                ? 'Thêm, sửa hoặc xoá câu hỏi, rồi lưu thay đổi vào bài quiz đã lưu.'
                : 'Tự soạn quiz từ đầu, hoặc tải lên quiz JSON/TXT có sẵn để thêm, sửa, xoá câu hỏi. Tải kết quả về rồi tải lại ở trang chủ để làm quiz.'}
            </p>
          </div>

          <Pagination
            page={currentPage}
            totalPages={totalPages}
            onChange={setPage}
            className="mb-5"
          />

          <div className="space-y-5">
            {questions
              .slice(currentPage * PER_PAGE, currentPage * PER_PAGE + PER_PAGE)
              .map((q, i) => {
                // Absolute index into `questions` so edits/removes hit the right one.
                const idx = currentPage * PER_PAGE + i;
                return (
                  <QuestionEditor
                    key={idx}
                    question={q}
                    index={idx}
                    onChange={(updated) => updateQuestion(idx, updated)}
                    onRemove={() => removeQuestion(idx)}
                    canRemove={questions.length > 1}
                  />
                );
              })}
          </div>

          <Button type="button" onClick={addQuestion} className="w-full mt-6">
            Thêm câu hỏi
          </Button>

          <Pagination
            page={currentPage}
            totalPages={totalPages}
            onChange={setPage}
            className="mt-6"
          />

          <div className={`mt-8 p-5 ${classes.innerBg} rounded-xl space-y-4`}>
            {isEditing && (
              <Button
                type="button"
                variant="success"
                onClick={handleSaveEdit}
                className="w-full font-semibold"
                title="Lưu thay đổi và về trang tải lên"
              >
                Lưu thay đổi
              </Button>
            )}

            <div>
              <label
                htmlFor="quizFilename"
                className={`block text-sm font-medium ${classes.mutedText} mb-1`}
              >
                Tên tệp
              </label>
              <input
                id="quizFilename"
                type="text"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                className={`w-full px-4 py-2 border-2 ${classes.inputBg} rounded-lg focus:outline-none focus:border-indigo-500`}
                placeholder="my-quiz"
              />
            </div>

            {!isEditing && (
              <>
                <div className="flex flex-col sm:flex-row gap-3">
                  <Button
                    type="button"
                    onClick={() => handleDownload('json')}
                    className="flex-1"
                    title="Tải về dạng .json"
                  >
                    Tải về dạng .json
                  </Button>
                  <Button
                    type="button"
                    variant="purple"
                    onClick={() => handleDownload('txt')}
                    className="flex-1"
                    title="Tải về dạng .txt"
                  >
                    Tải về dạng .txt
                  </Button>
                </div>

                <p className={`text-xs ${classes.mutedText}`}>
                  Hai định dạng có cùng nội dung JSON. Chọn đuôi tệp bạn muốn.
                </p>
              </>
            )}

            <ErrorBanner>{error}</ErrorBanner>
          </div>
        </div>
      </div>

      {showExitModal && (
        <Modal
          title="Bỏ bài quiz này?"
          description="Bài quiz chưa lưu sẽ mất. Hãy tải về trước nếu muốn giữ."
        >
          <Button type="button" variant="danger" onClick={confirmExit} className="w-full">
            Có, bỏ đi
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => setShowExitModal(false)}
            className="w-full"
          >
            Huỷ
          </Button>
        </Modal>
      )}

      {showHistoryWarn && (
        <Modal
          title="Lưu thay đổi?"
          description="Sửa sẽ làm đổi bài quiz này nên các lần làm đã lưu không còn xem lại được, chỉ giữ điểm cuối trong lịch sử kết quả."
        >
          <Button type="button" variant="success" onClick={performSaveEdit} className="w-full">
            Lưu thay đổi
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => setShowHistoryWarn(false)}
            className="w-full"
          >
            Huỷ
          </Button>
        </Modal>
      )}

      {pendingImport && (
        <Modal
          title="Thay bài quiz hiện tại?"
          description="Tải lên sẽ thay các câu hỏi hiện có. Không hoàn tác được."
        >
          <Button type="button" variant="emerald" onClick={confirmImport} className="w-full">
            Thay thế
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => setPendingImport(null)}
            className="w-full"
          >
            Huỷ
          </Button>
        </Modal>
      )}
    </div>
  );
};

export default QuizCreatorPage;
