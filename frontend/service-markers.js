// Static category symbols shared by SDK and fallback maps. No provider HTML is used.
export function serviceIcon(category){
 const paths={CAFE:'M4 7h12v7a5 5 0 0 1-10 0V7m10 1h2a3 3 0 0 1 0 6h-2M3 21h16M8 2v2m4-2v2',RESTAURANT:'M5 3v7m3-7v7m3-7v7M5 8h6m-3 2v11M19 3v18m0-18c-4 3-4 8 0 8',TEA_DRINK:'M6 7h12l-2 14H8L6 7Zm6 0 3-5h5M4 7h16',DESSERT_ICE_CREAM:'m7 11 5 11 5-11M7 11a4 4 0 0 1-1-7 5 5 0 0 1 10 0 4 4 0 0 1 1 7Z',CONVENIENCE_STORE:'M3 9h18l-2-6H5L3 9Zm2 0v12h14V9M9 21v-7h6v7',RESTROOM:'M8 4h.01M16 4h.01M6 8h4v6H6V8Zm2 6v7m6-13h4l2 7h-8l2-7Zm2 7v6',MALL:'M4 8h16v13H4V8Zm4 0V6a4 4 0 0 1 8 0v2'};
 return `<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[category]||paths.MALL}"/></svg>`;
}
export function visibleServices(nearby,guidance){return ['nearby_detour','return_to_route'].includes(guidance?.kind)?[]:nearby;}
