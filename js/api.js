export async function api(path, method='GET', body){
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(`/api/${path}`, opts);
  const data = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
export const register = (email,password,name)=>api('auth_register.php','POST',{email,password,name});
export const login    = (email,password)=>api('auth_login.php','POST',{email,password});
export const logout   = ()=>api('auth_logout.php','POST',{});
export const me       = ()=>api('me.php','GET');
export const createOrder = (items)=>api('create_order.php','POST',{items});
export const myOrders = ()=>api('my_orders.php','GET');
