/**
 * mockServices.js — Legacy re-export shim
 *
 * Dashboard.jsx now imports from apiService.js directly.
 * This file re-exports everything from the real service so that
 * any other file that still imports from mockServices.js keeps working.
 */
export { api, useLiveStream } from './apiService';
