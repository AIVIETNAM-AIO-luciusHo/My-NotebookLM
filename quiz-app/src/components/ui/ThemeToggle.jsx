import { useTheme } from '../../contexts/useTheme';
import { IconSun, IconMoon } from './icons';

// compact=true → small borderless icon button for use inside header bars
const ThemeToggle = ({ compact = false }) => {
  const { isDarkMode, setIsDarkMode } = useTheme();

  if (compact) {
    return (
      <button
        onClick={() => setIsDarkMode(!isDarkMode)}
        className={`p-1.5 rounded-lg transition-colors ${
          isDarkMode ? 'text-gray-400 hover:text-yellow-400 hover:bg-gray-800' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
        }`}
        aria-label="Toggle theme"
        title={isDarkMode ? 'Light mode' : 'Dark mode'}
      >
        {isDarkMode ? <IconSun className="w-4 h-4" /> : <IconMoon className="w-4 h-4" />}
      </button>
    );
  }

  return (
    <button
      onClick={() => setIsDarkMode(!isDarkMode)}
      className={`p-3 rounded-full shadow-lg transition-all ${
        isDarkMode ? 'bg-gray-800 text-yellow-400' : 'bg-white text-gray-800'
      }`}
      aria-label="Toggle theme"
      title={isDarkMode ? 'Turn to light mode' : 'Turn to dark mode'}
    >
      {isDarkMode ? <IconSun className="w-6 h-6" /> : <IconMoon className="w-6 h-6" />}
    </button>
  );
};

export default ThemeToggle;
