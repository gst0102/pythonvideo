const API_BASE = "http://127.0.0.1:8000";

export interface UserAccount {
  total_points: number;
  withdrawable_points: number;
  frozen_points: number;
  consumable_points: number;
}

export interface NetdiskResource {
  id: string;
  title: string;
  category: string;
  pan: string;
  level: "normal" | "featured" | "official" | string;
  cost_points: number;
  verified_at: string;
  downloads: number;
  favorites: number;
  description: string;
  is_active: boolean;
}

export interface NetdiskResourceAccess {
  unlocked: boolean;
  ledger_id: string;
  points_delta: number;
  link: string;
  extract_code: string;
  unzip_code: string;
}

export interface ResourceDetailResponse {
  resource: NetdiskResource;
}

export interface ResourceAccessResponse {
  resource: NetdiskResource;
  access: NetdiskResourceAccess;
  account: UserAccount;
}

export interface ResourceUnlockResponse {
  resource: NetdiskResource;
  unlock: NetdiskResourceAccess;
  account: UserAccount;
}

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

export const setToken = (token: string) => {
  uni.setStorageSync("token", token);
  uni.setStorageSync("access_token", token);
};

export const ensureDevLogin = async () => {
  const existing = getToken();
  if (existing) return existing;
  const data = await request<{ token: string }>("/user/dev-login", {
    method: "POST",
    data: {
      openid: "netdisk-dev-user",
      nickname: "本地测试用户",
      avatar: "",
      seed_points: 200
    }
  });
  setToken(data.token);
  return data.token;
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

export const getNetdiskResourceDetail = (id: string) => {
  return request<ResourceDetailResponse>(`/netdisk/resources/${id}`);
};

export const getNetdiskResourceAccess = (id: string) => {
  return request<ResourceAccessResponse>(`/netdisk/resources/${id}/access`);
};

export const unlockNetdiskResource = (id: string) => {
  return request<ResourceUnlockResponse>(`/netdisk/resources/${id}/unlock`, { method: "POST" });
};
