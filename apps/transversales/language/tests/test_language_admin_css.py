/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

// Charger le CSS
const cssContent = fs.readFileSync(
  path.resolve(__dirname, '../static/language/language_admin.css'),
  'utf8'
);

describe('language_admin.css', () => {
  beforeEach(() => {
    // Réinitialiser le DOM
    document.body.innerHTML = `
      <div class="language-admin">
        <div class="form-warning">Warning</div>
        <input class="language-code-input" />
        <label class="field-code">Code</label>
        <div class="stats-cards">
          <div class="stat">Stat 1</div>
        </div>
        <table class="stats-table">
          <thead><tr><th>Header</th></tr></thead>
          <tbody><tr><td>Data</td></tr></tbody>
        </table>
        <ul class="error-list"><li>Error</li></ul>
        <div class="actions"><button class="button">Action</button></div>
        <span class="spinner">⏳</span>
      </div>
    `;
    
    // Injecter le CSS
    const style = document.createElement('style');
    style.textContent = cssContent;
    document.head.appendChild(style);
  });

  test('applies form-warning styles', () => {
    const warning = document.querySelector('.form-warning');
    const styles = window.getComputedStyle(warning);
    expect(styles.color).toBe('rgb(187, 17, 17)'); // --error-fg: #b11
    expect(styles.backgroundColor).toBe('rgb(255, 238, 238)'); // --error-bg: #fee
    expect(styles.borderLeft).toBe('3px solid rgb(187, 17, 17)');
  });

  test('applies language-code-input styles', () => {
    const input = document.querySelector('.language-code-input');
    const styles = window.getComputedStyle(input);
    expect(styles.fontFamily).toContain('monospace');
    expect(styles.border).toBe('1px solid rgb(204, 204, 204)'); // --border-color: #ccc
    expect(styles.boxSizing).toBe('border-box');
  });

  test('applies focus styles for language-code-input', () => {
    const input = document.querySelector('.language-code-input');
    input.focus();
    const styles = window.getComputedStyle(input);
    expect(styles.borderColor).toBe('rgb(68, 126, 155)'); // --link-fg: #447e9b
    expect(styles.outline).toBe('rgb(68, 126, 155) solid 2px'); // --link-fg
  });

  test('applies field-code label hint', () => {
    const label = document.querySelector('.field-code');
    expect(label.textContent).toContain('(ex: fr, en, pt-br)');
    const styles = window.getComputedStyle(label.querySelector('label::after'));
    expect(styles.color).toBe('rgb(102, 102, 102)'); // --body-quiet-color: #666
  });

  test('applies stats-cards styles', () => {
    const statsCards = document.querySelector('.stats-cards');
    const stat = document.querySelector('.stat');
    const cardsStyles = window.getComputedStyle(statsCards);
    const statStyles = window.getComputedStyle(stat);
    expect(cardsStyles.display).toBe('flex');
    expect(cardsStyles.gap).toBe('20px');
    expect(statStyles.backgroundColor).toBe('rgb(248, 248, 248)'); // --module-bg: #f8f8f8
    expect(statStyles.borderRadius).toBe('4px');
  });

  test('applies stats-table styles', () => {
    const table = document.querySelector('.stats-table');
    const th = document.querySelector('.stats-table th');
    const styles = window.getComputedStyle(table);
    const thStyles = window.getComputedStyle(th);
    expect(styles.borderCollapse).toBe('collapse');
    expect(thStyles.border).toBe('1px solid rgb(204, 204, 204)'); // --border-color: #ccc
    expect(thStyles.padding).toBe('8px');
  });

  test('applies spinner styles', () => {
    const spinner = document.querySelector('.spinner');
    const styles = window.getComputedStyle(spinner);
    expect(spinner.getAttribute('aria-hidden')).toBe('true');
    expect(styles.animation).toContain('spin');
  });

  test('applies responsive styles for max-width: 600px', () => {
    // Simuler petite résolution
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 500 });
    window.dispatchEvent(new Event('resize'));
    
    const statsCards = document.querySelector('.stats-cards');
    const styles = window.getComputedStyle(statsCards);
    expect(styles.flexDirection).toBe('column');
    
    const button = document.querySelector('.actions .button');
    const buttonStyles = window.getComputedStyle(button);
    expect(buttonStyles.display).toBe('block');
  });

  test('applies high-contrast styles', () => {
    // Simuler prefers-contrast: high
    window.matchMedia = jest.fn().mockImplementation(query => ({
      matches: query === '(prefers-contrast: high)',
      addListener: jest.fn(),
      removeListener: jest.fn(),
    }));
    
    const warning = document.querySelector('.form-warning');
    const styles = window.getComputedStyle(warning);
    expect(styles.backgroundColor).toBe('rgb(0, 0, 0)');
    expect(styles.color).toBe('rgb(255, 255, 255)');
    expect(styles.borderLeft).toBe('3px solid rgb(255, 255, 255)');
  });

  test('applies print styles', () => {
    // Simuler media print
    window.matchMedia = jest.fn().mockImplementation(query => ({
      matches: query === 'print',
      addListener: jest.fn(),
      removeListener: jest.fn(),
    }));
    
    const spinner = document.querySelector('.spinner');
    const actions = document.querySelector('.actions');
    const spinnerStyles = window.getComputedStyle(spinner);
    const actionsStyles = window.getComputedStyle(actions);
    expect(spinnerStyles.display).toBe('none');
    expect(actionsStyles.display).toBe('none');
  });
});
