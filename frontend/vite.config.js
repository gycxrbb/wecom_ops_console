import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
export default defineConfig({
    plugins: [vue()],
    resolve: {
        alias: {
            '#': path.resolve(__dirname, './src')
        }
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                secure: false,
                configure: function (proxy) {
                    proxy.on('proxyRes', function (proxyRes) {
                        var _a;
                        if ((_a = proxyRes.headers['content-type']) === null || _a === void 0 ? void 0 : _a.includes('text/event-stream')) {
                            proxyRes.headers['x-accel-buffering'] = 'no';
                            proxyRes.headers['cache-control'] = 'no-cache, no-transform';
                            delete proxyRes.headers['content-encoding'];
                            delete proxyRes.headers['content-length'];
                        }
                    });
                },
            },
            '/auth': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                secure: false,
            }
        }
    }
});
