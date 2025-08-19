/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

// Charger le script language_admin.js
const scriptContent = fs.readFileSync(
  path.resolve(__dirname, '../static/language/language_admin.js'),
  'utf8'
);

// Exécuter le script dans l'environnement JSDOM
new Function(scriptContent)();

// Mock pour window.gettext
const mockGettext = jest.fn(msg => msg);
window.gettext = mockGettext;

describe('language_admin.js', () => {
  beforeEach(() => {
    // Réinitialiser le DOM avant chaque test
    document.body.innerHTML = `
      <form>
        <div class="form-row field-code">
          <input id="id_code" class="language-code-input" type="text" />
          <input id="id_name" class="language-name-input" type="text" />
          <input id="id_is_active" class="language-is-active-input" type="checkbox" />
          <input id="id_is_default" class="language-is-default-input" type="checkbox" />
        </div>
        <button data-task="rerun">Rerun</button>
      </form>
    `;
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.clearAllMocks();
  });

  describe('normalizeCode', () => {
    test('normalizes valid locale codes', () => {
      expect(normalizeCode('PT_BR')).toBe('pt-br');
      expect(normalizeCode('  FR  ')).toBe('fr');
      expect(normalizeCode('en')).toBe('en');
    });

    test('handles empty or invalid input', () => {
      expect(normalizeCode('')).toBe('');
      expect(normalizeCode(null)).toBe('');
    });
  });

  describe('code input validation', () => {
    test('validates correct code on blur', () => {
      const codeInput = document.querySelector('#id_code');
      codeInput.value = 'en';
      const blurEvent = new Event('blur');
      codeInput.dispatchEvent(blurEvent);
      
      jest.runAllTimers(); // Exécuter debounce
      expect(codeInput.value).toBe('en');
      expect(document.querySelector('.form-warning')).toBeNull();
      expect(mockGettext).not.toHaveBeenCalled();
    });

    test('shows warning for invalid code', () => {
      const codeInput = document.querySelector('#id_code');
      codeInput.value = 'xyz';
      const blurEvent = new Event('blur');
      codeInput.dispatchEvent(blurEvent);
      
      jest.runAllTimers();
      const warning = document.querySelector('.form-warning');
      expect(warning).not.toBeNull();
      expect(warning.textContent).toBe('Invalid language code (e.g., \'fr\', \'pt-br\').');
      expect(warning.getAttribute('role')).toBe('alert');
      expect(codeInput.getAttribute('aria-describedby')).toBe('language-code-warning');
      expect(mockGettext).toHaveBeenCalledWith('Invalid language code (e.g., \'fr\', \'pt-br\').');
    });

    test('removes warning on valid code after invalid', () => {
      const codeInput = document.querySelector('#id_code');
      codeInput.value = 'xyz';
      codeInput.dispatchEvent(new Event('blur'));
      jest.runAllTimers();
      
      codeInput.value = 'fr';
      codeInput.dispatchEvent(new Event('blur'));
      jest.runAllTimers();
      
      expect(document.querySelector('.form-warning')).toBeNull();
      expect(codeInput.getAttribute('aria-describedby')).toBeNull();
    });
  });

  describe('is_default implies is_active', () => {
    test('forces is_active when is_default is checked', () => {
      const isDefaultInput = document.querySelector('#id_is_default');
      const isActiveInput = document.querySelector('#id_is_active');
      isActiveInput.checked = false;
      isDefaultInput.checked = true;
      
      const changeEvent = new Event('change');
      isDefaultInput.dispatchEvent(changeEvent);
      
      expect(isActiveInput.checked).toBe(true);
      const warning = document.querySelector('.form-warning');
      expect(warning.textContent).toBe('Default language must be active.');
      expect(isDefaultInput.getAttribute('aria-describedby')).toBe('language-code-warning');
      expect(mockGettext).toHaveBeenCalledWith('Default language must be active.');
    });

    test('removes warning when is_active is checked', () => {
      const isDefaultInput = document.querySelector('#id_is_default');
      const isActiveInput = document.querySelector('#id_is_active');
      isActiveInput.checked = true;
      isDefaultInput.checked = true;
      
      const changeEvent = new Event('change');
      isDefaultInput.dispatchEvent(changeEvent);
      
      expect(document.querySelector('.form-warning')).toBeNull();
      expect(isDefaultInput.getAttribute('aria-describedby')).toBeNull();
    });
  });

  describe('spinner for task buttons', () => {
    test('adds spinner and disables button on click', () => {
      const button = document.querySelector('button[data-task="rerun"]');
      const clickEvent = new Event('click');
      button.dispatchEvent(clickEvent);
      
      const spinner = document.querySelector('.spinner');
      expect(spinner).not.toBeNull();
      expect(spinner.textContent).toBe('⏳');
      expect(spinner.getAttribute('aria-hidden')).toBe('true');
      expect(button.getAttribute('aria-busy')).toBe('true');
      expect(button.disabled).toBe(true);
    });

    test('ignores click if button already disabled', () => {
      const button = document.querySelector('button[data-task="rerun"]');
      button.disabled = true;
      const clickEvent = new Event('click');
      button.dispatchEvent(clickEvent);
      
      expect(document.querySelector('.spinner')).toBeNull();
    });
  });

  describe('missing form fields', () => {
    test('logs error if required fields are missing', () => {
      document.body.innerHTML = '<form></form>'; // Form vide
      console.error = jest.fn();
      
      // Relancer l'événement DOMContentLoaded
      const script = document.createElement('script');
      script.textContent = scriptContent;
      document.body.appendChild(script);
      document.dispatchEvent(new Event('DOMContentLoaded'));
      
      expect(console.error).toHaveBeenCalledWith('Required form fields missing.');
    });
  });

  describe('debounce on blur', () => {
    test('debounces multiple blur events', () => {
      const codeInput = document.querySelector('#id_code');
      codeInput.value = 'xyz';
      const blurEvent = new Event('blur');
      
      // Simuler plusieurs blur rapides
      codeInput.dispatchEvent(blurEvent);
      codeInput.dispatchEvent(blurEvent);
      codeInput.dispatchEvent(blurEvent);
      
      expect(document.querySelector('.form-warning')).toBeNull(); // Pas encore affiché
      jest.runAllTimers(); // Exécuter debounce
      expect(document.querySelector('.form-warning')).not.toBeNull();
      expect(mockGettext).toHaveBeenCalledTimes(1); // Une seule validation
    });
  });

  describe('i18n fallback', () => {
    test('falls back to identity if gettext is missing', () => {
      window.gettext = undefined;
      const codeInput = document.querySelector('#id_code');
      codeInput.value = 'xyz';
      const blurEvent = new Event('blur');
      codeInput.dispatchEvent(blurEvent);
      
      jest.runAllTimers();
      const warning = document.querySelector('.form-warning');
      expect(warning.textContent).toBe('Invalid language code (e.g., \'fr\', \'pt-br\').');
    });
  });
});
