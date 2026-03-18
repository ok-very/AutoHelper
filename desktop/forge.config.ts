import type { ForgeConfig } from "@electron-forge/shared-types";
import { MakerSquirrel } from "@electron-forge/maker-squirrel";
import { VitePlugin } from "@electron-forge/plugin-vite";

const config: ForgeConfig = {
  packagerConfig: {
    name: "AutoHelper",
    icon: "./resources/icon",
    extraResource: ["./autohelper", "./resources/tray-idle.png", "./resources/tray-working.png"],
    asar: false,
  },
  makers: [
    new MakerSquirrel({
      name: "AutoHelper",
      setupIcon: "./resources/icon.ico",
    }),
  ],
  plugins: [
    new VitePlugin({
      build: [
        {
          entry: "src/main/index.ts",
          config: "vite.main.config.ts",
        },
        {
          entry: "src/preload/index.ts",
          config: "vite.preload.config.ts",
        },
      ],
      // No renderer — we load the FastAPI dashboard via URL
      renderer: [],
    }),
  ],
};

export default config;
