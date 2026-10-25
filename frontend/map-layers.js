// Each layer owns its overlays. Replacing a detour cannot touch the main route.
export class MapLayers {
 constructor(map){this.map=map;this.layers=new Map();this.signatures=new Map();}
 replace(name,signature,create){if(this.signatures.get(name)===signature)return false;this.clear(name);const objects=create();this.layers.set(name,objects);this.signatures.set(name,signature);if(objects.length)this.map.add(objects);return true;}
 clear(name){const objects=this.layers.get(name);if(objects?.length)this.map.remove(objects);this.layers.delete(name);this.signatures.delete(name);}
 objects(name){return this.layers.get(name)||[];}
 destroy(){for(const name of [...this.layers.keys()])this.clear(name);}
}
export const routeStyle={strokeColor:'#8053DB',strokeWeight:8,isOutline:true,outlineColor:'#22222A',borderWeight:2,showDir:true,lineCap:'round',lineJoin:'round',zIndex:45};
export const auxiliaryStyle=kind=>({...routeStyle,strokeColor:kind==='start_access'?'#D99A39':'#20A89A',strokeWeight:kind==='start_access'?7:5,strokeStyle:kind==='start_access'?'solid':'dashed',showDir:kind==='start_access',zIndex:48});
