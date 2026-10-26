import test from 'node:test';
import assert from 'node:assert/strict';
import {serviceIcon,visibleServices} from '../service-markers.js';
test('all service categories have distinct safe symbols',()=>{const categories=['CAFE','RESTAURANT','TEA_DRINK','DESSERT_ICE_CREAM','CONVENIENCE_STORE','RESTROOM','MALL'];assert.equal(new Set(categories.map(serviceIcon)).size,7);assert.equal(serviceIcon('<img onerror=x>'),serviceIcon('MALL'));});
test('detour and return hide all provider markers, clearing guidance restores them',()=>{const list=[{id:'coffee'},{id:'food'}];assert.deepEqual(visibleServices(list,{kind:'nearby_detour'}),[]);assert.deepEqual(visibleServices(list,{kind:'return_to_route'}),[]);assert.equal(visibleServices(list,null),list);assert.equal(visibleServices(list,{kind:'start_access'}),list);});
