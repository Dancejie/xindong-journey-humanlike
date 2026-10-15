import { changeLanguage, gameLanguage, GameLanguage, isEnglish } from './i18n'

export function LanguageSwitch({ disabled = false }: { disabled?: boolean }) {
  return <label className="language-control">
    <span className="visually-hidden">{isEnglish ? 'Language' : '语言'}</span>
    <select value={gameLanguage} disabled={disabled} aria-label={isEnglish ? 'Choose language' : '选择语言'} onChange={event => changeLanguage(event.currentTarget.value as GameLanguage)}>
      <option value="en">EN</option>
      <option value="zh-CN">中文</option>
    </select>
  </label>
}
