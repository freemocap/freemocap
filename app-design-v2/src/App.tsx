import {Provider} from 'react-redux';
import AppLayout from "./components/layout/AppLayout.tsx";
import {store} from "./store";

function App() {
    return (
        <Provider store={store}>
            <AppLayout />
        </Provider>
    );
}

export default App;
