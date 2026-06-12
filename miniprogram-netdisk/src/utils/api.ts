const API_BASE = "http://127.0.0.1:8000";

export interface NetdiskNotification {
  id: string;
  notice_type: string;
  title: string;
  content: string;
  related_type: string;
  related_id: string;
  status: string;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NetdiskNotification[];
  unread_count: number;
}

const getToken = () => {
  return uni.getStorageSync("token") || uni.getStorageSync("access_token") || "";
};

export const request = <T>(url: string, options: UniApp.RequestOptions = {}) => {
  return new Promise<T>((resolve, reject) => {
    const token = getToken();
    uni.request({
      ...options,
      url: `${API_BASE}${url}`,
      header: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.header || {})
      },
      success: (res) => {
        const data: any = res.data || {};
        if (data.code === 200 || data.code === 0) {
          resolve((data.data ?? data) as T);
          return;
        }
        reject(new Error(data.msg || data.message || "请求失败"));
      },
      fail: () => reject(new Error("后端服务暂不可用"))
    });
  });
};

export const getNetdiskNotifications = () => {
  return request<NotificationListResponse>("/netdisk/notifications");
};

export const markNetdiskNotificationRead = (id: string) => {
  return request<NetdiskNotification>(`/netdisk/notifications/${id}/read`, { method: "POST" });
};
