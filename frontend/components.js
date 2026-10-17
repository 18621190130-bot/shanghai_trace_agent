import {safePoiImageUrl} from './poi-images.js';
import {escapeHTML as e,safeAsset} from './lib.js';
export function icon(name) {
  const paths={arrow:'M4 12h15m-6-6 6 6-6 6',back:'M20 12H5m6-6-6 6 6 6',close:'m6 6 12 12M6 18 18 6',plus:'M12 5v14M5 12h14',minus:'M5 12h14',
    compass:'m16 8-3 5-5 3 3-5 5-3ZM12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z',fit:'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5',
    location:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v3m0 14v3M2 12h3m14 0h3',check:'m5 12 4 4L19 6',sun:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1',
    walk:'m10 4 2 0m-5 8 3-5 4 3 4 1m-7-1-1 6-4 5m5-6 4 6',chevron:'m8 5 7 7-7 7',pause:'M9 5v14M15 5v14',play:'m8 5 11 7-11 7V5Z',menu:'M4 7h16M4 12h16M4 17h16',search:'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm5 12 6 6'};
  return `<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[name]||paths.arrow}"/></svg>`;
}
export const button=(label,action,style='primary',extra='')=>`<button class="button ${style}" data-action="${action}" ${extra}>${e(label)}${style.split(' ').includes('primary')?icon('arrow'):''}</button>`;
export const iconButton=(name,label,action)=>`<button class="icon-button" aria-label="${e(label)}" title="${e(label)}" data-action="${action}">${icon(name)}</button>`;
export function imageSlot(slot={},label='',className='',id='') {
  const src=safePoiImageUrl(slot?.src,slot?.source);
  return `<div class="image-slot ${e(slot?.theme||'stone')} ${className}" ${id?`data-slot="${e(id)}"`:''}>
    ${src?`<img src="${e(src)}" alt="${e(slot.alt||label)}" loading="lazy" referrerpolicy="no-referrer">`:''}<span class="slot-frame" aria-hidden="true"><i></i></span><span class="slot-label">${e(label)}</span>
  </div>`;
}
export const skeleton=()=>'<div class="skeleton" aria-hidden="true"></div><div class="skeleton short" aria-hidden="true"></div>';
export function openingStatus(info,t) {
  const status=info?.open_status;
  return `<span class="status-text ${status==='OPEN'?'positive':''}">${e(t(status==='NOT_APPLICABLE'?'notApplicable':status==='OPEN'?'open':status==='CLOSED'?'closed':'openingUnknown'))}</span>`;
}
export function culturalBridge(content,lang,t) {
  const copy=content?.[lang];
  if(!copy)return `<section class="cultural-story reserved"><span class="eyebrow">${e(t('cultureEyebrow'))}</span><span class="bridge-symbol" aria-hidden="true">↔</span><h3>${e(t('storyReserved'))}</h3><p>${e(t('storyReservedCopy'))}</p><div class="story-lines" aria-hidden="true"><i></i><i></i><i></i></div></section>`;
  return `<section class="cultural-story"><span class="eyebrow">${e(t('cultureEyebrow'))}</span>${Array.isArray(copy.paragraphs)?copy.paragraphs.filter(p=>typeof p==='string').map(p=>`<p>${e(p)}</p>`).join(''):''}${[['why_matters','whyMatters'],['bridge','bridge'],['look_for','lookFor'],['local_context','localContext']].filter(([key])=>copy[key]).map(([key,title])=>`<section><h3>${e(t(title))}</h3><p>${e(copy[key])}</p></section>`).join('')}</section>`;
}
