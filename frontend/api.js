export class ApiError extends Error {constructor(code){super(code);this.code=code;}}
export async function request(path,body,options={}) {
  let response;
  try {response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:options.signal,credentials:'same-origin'});}
  catch(error){if(error.name==='AbortError')throw error;throw new ApiError('networkError');}
  let data;
  try{data=await response.json();}catch{throw new ApiError('server_error');}
  if(!response.ok)throw new ApiError(data.error||'server_error');
  return data;
}
export const api={bootstrap:()=>request('/api/bootstrap'),generate:body=>request('/api/generate',body),
  clarify:body=>request('/api/clarify',body),action:body=>request('/api/trip/action',body),
  turn:body=>request('/api/trip/turn',body),reality:body=>request('/api/reality',body),poi:poi_id=>request('/api/poi',{poi_id}),
  nearby:body=>request('/api/nearby',body),content:()=>request('/content.json')};
