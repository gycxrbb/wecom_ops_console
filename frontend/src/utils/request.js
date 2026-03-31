import axios from 'axios';
import { ElMessage } from 'element-plus';
const service = axios.create({
    baseURL: '/api',
    timeout: 50000,
    withCredentials: true
});
service.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers['Authorization'] = 'Bearer ' + token;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});
service.interceptors.response.use((response) => {
    const res = response.data;
    // Backend V2 format compatibility
    if (res.code !== undefined) {
        if (res.code !== 0 && res.code !== 200) {
            ElMessage.error(res.message || '系统错误');
            if (res.code === 40100 || res.code === 401) {
                window.location.href = '/login';
            }
            return Promise.reject(new Error(res.message || '系统错误'));
        }
        return res.data;
    }
    return res;
}, (error) => {
    if (error.response?.status === 401) {
        window.location.href = '/login';
    }
    else {
        ElMessage({
            message: error.response?.data?.detail || error.message || '请求失败',
            type: 'error',
            duration: 5 * 1000
        });
    }
    return Promise.reject(error);
});
export default service;
//# sourceMappingURL=request.js.map