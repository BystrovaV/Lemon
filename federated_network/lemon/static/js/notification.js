class NotificationDom {
    constructor(user, name, username, msg, url, type) {
        this.timeToDisappear = 20000;
        this.url = url;
        this.type = type;
        
        this.user = user;

        this.notification = document.createElement('div');
        var p_title = document.createElement('p');
        var p_subtitle = document.createElement('p');
        var p_msg = document.createElement('p');
        var btn = document.createElement('button');

        p_title.innerText = name;
        p_subtitle.innerText = username;
        p_msg.innerText = msg;

        this.notification.className = 'notification';
        p_msg.className = 'notification_msg';
        btn.className = 'btn-white-close';

        btn.addEventListener('click', this.closeClick.bind(this));

        this.notification.appendChild(btn);
        this.notification.appendChild(p_title);
        this.notification.appendChild(p_subtitle);
        this.notification.appendChild(p_msg);

        this.notification.style.transition = `opacity ${this.timeToDisappear / 1000}s linear`;
        setTimeout(() => {
            this.notification.style.opacity = 0;
          }, this.timeToDisappear);

        this.notification.addEventListener('transitionend', () => {
            this.notification.remove();
        });

        this.notification.addEventListener('click', this.notificationClick.bind(this));
    }

    notificationClick () {
        var str = this.url;

        if (this.type == "message") {
            str = str.substring(7);

            var hostname = str.substring(0, str.indexOf('/')).split('.');
            str = str.substring(str.indexOf('/') + 1);
    
            var slices = str.split('/');
    
            var path = "http://" + window.location.host + "/@" + this.user + "/inbox" + "?" + "host=" + hostname[0] + "&domen=" + hostname[1] + "&actor="
                + slices[0] + "&id=" + slices[2];
    
            window.location.href = path;
        } else if (this.type = "like") {
            window.location.href = this.url;
        } else if (this.type = "follow") {
            window.open(this.url);
        }
        
    }

    closeClick(event) {
        event.cancelBubble = true;
        if(event.stopPropagation) 
            event.stopPropagation();
        this.notification.remove();
    }
}

class CountMessage {
    constructor() {
        this.element = document.createElement('div');
        this.element.className = 'count-msg';
        this.element.id = 'count-msg';

        this.isShow = false;
    }

    changeCount(cnt) {
        if (cnt != 0) {
            this.element.textContent = cnt;
            this.show();
        } else {
            this.delete();
        }
    }

    show() {
        if (!this.isShow) {
            this.isShow = true;

            var inbox = document.getElementById('nav__inbox');
            if (inbox != undefined) {
                inbox.appendChild(this.element);
            }
        }
    }

    delete() {
        document.removeChild(this.element);
    }
}

class NewMessage {
    constructor(activity) {
        console.log(activity);

        if (window.location.pathname.includes("inbox")) {
            if (data.length == 0) {
                location.reload();
            }

            var element = document.createElement('div');
            element.classList.add('item','item0');
            if (activity['type'] == 'Create') {
                element.classList.add('create');
            }

            if (activity['is_read'] == 1) {
                element.classList.add('is_read');
            }

            element.id = activity['id'];

            var itemLeft = document.createElement('div');
            itemLeft.className = 'item__left';

            var temp = document.createElement('h2');
            temp.innerText = activity['type'];
            temp.className = 'item__type';
            itemLeft.appendChild(temp);

            temp = document.createElement('p');
            temp.innerText = activity['actor'];
            temp.className = 'item__to';
            itemLeft.appendChild(temp);

            element.appendChild(itemLeft);

            var itemContent = document.createElement('div');
            itemContent.className = 'item__content__wrap';

            temp = document.createElement('p');
            temp.className = 'item__content';
            if (activity['type'] == 'Create') {
                temp.innerText = activity['object']['content'];
            } else if (activity['type'] == 'Follow') {
                temp.innerText = activity['actor'] + ' followed you!';
            } else if (activity['type'] == 'Like') {
                temp.innerText = activity['actor'] + ' liked your post\n' + activity['object'] + "!";
            } else if (activity['type'] == 'Undo') {
                temp.innerText = activity['actor'] + ' don\'t like your post\n' + activity['object'] + " anymore!";
            }
            
            itemContent.appendChild(temp);
            element.appendChild(itemContent);
            
            var imgElement = document.createElement("img");
            imgElement.classList.add("remove__img");
            imgElement.src = "/static/lemon/img/remove.png";
            element.appendChild(imgElement);

            $(element).hide();
            $(element).insertBefore($(document.getElementById(data[0].id)));

            data.unshift(activity);
            this.show();
            // console.log(data);
        }
    }

    show() {
        for (var i = 0; i < data.length; i++) {
            var item =  $(document.getElementById(data[i].id));
            item.show();

            if (item.is(":visible")) {
                if (i % 2 == 0) {
                    item.removeClass("item0");
                    item.addClass("item1");
                } else {
                    item.removeClass("item1");
                    item.addClass("item0");
                }
                //temp++;
            }
        }
    }
}

class UserWebSocket {
    constructor(username) {
        this.socket = null;
        this.username = username;
        this.countMsg = new CountMessage();
    }

    connect() {
        this.socket = new WebSocket (
            'ws://'
            + window.location.host
            + '/ws/users/'
            + this.username
            + '/'
        );

        this.socket.onopen = (event) => {
            console.log("WebSocket is open");
        }

        this.socket.onerror = (event) => {
            console.error('WebSocket error:', event);
        };
      
        this.socket.onclose = (event) => {
            console.log('WebSocket connection closed:', event);
        };

        this.socket.onmessage = this.recieve.bind(this);
    }

    recieve(e) {
        const data = JSON.parse(e.data);

        if (data.msg_type == "cnt_msg") {
            this.countMsg.changeCount(data.message);
        } else {
            var notification = new NotificationDom(this.username, data.actor_name, 
                data.actor_username, data.message, data.url, data.msg_type);
    
            var newMes = new NewMessage(data.activity);
            document.body.appendChild(notification.notification);
        }
    }

    sendIsRead(messageId, isRead) {
        if (this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(
                {
                    'type': 'is_read',
                    'message_id': messageId,
                    'message': isRead
                }
            ));
        } else {
            const myHandler = () => {
                this.socket.send(JSON.stringify({
                    'type': 'is_read',
                    'message_id': messageId,
                    'message': isRead
                }));

                this.socket.removeEventListener('open', myHandler);
            };

            this.socket.addEventListener('open', myHandler); 
        }
    }

    close() {
        this.socket.close();
    }
}