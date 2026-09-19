// electron.vite.config.ts
import { defineConfig } from "electron-vite";
import react from "@vitejs/plugin-react";
var electron_vite_config_default = defineConfig({
  main: {},
  preload: {},
  renderer: {
    plugins: [react()]
  }
});
export {
  electron_vite_config_default as default
};
