import 'axios';

declare module 'axios' {
  export interface AxiosInstance {
    request<T = any, R = any, D = any>(config: AxiosRequestConfig<D>): Promise<R>;
    get<T = any, R = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
    delete<T = any, R = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
    head<T = any, R = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
    options<T = any, R = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
    post<T = any, R = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
    put<T = any, R = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
    patch<T = any, R = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
  }
}